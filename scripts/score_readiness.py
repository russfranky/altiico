"""Score each collection's readiness for hubzz ingress.

A set is READY when all CRITICAL criteria pass. The readiness_score (0-8) also
counts completeness criteria so near-ready sets can be prioritised. Criteria are
grounded in the pre-alpha packages/avatars canonical schema (a set needs a
served VRM, a clear license, and an ownership/identity anchor).

  CRITICAL (gate ingress):
    vrm_ok       a reachable, valid VRM   (vrm_check_status == 'ok_vrm')
    license_ok   license is known & usable (license_category in green/yellow)
    identity_ok  has a name + an anchor    (contract, or an open/CC0 or arweave set)

  COMPLETENESS (for a full, polished set):
    banner_ok    banner_image_url present
    pfp_ok       image_url / sample_nft_image present
    desc_ok      description present
    social_ok    twitter or discord present
    count_ok     total_supply / avatar_count present
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent

CRITICAL = ("vrm_ok", "license_ok", "identity_ok")
COMPLETENESS = ("banner_ok", "pfp_ok", "desc_ok", "social_ok", "count_ok")


def _has(v: Any) -> bool:
    return v is not None and str(v).strip() != ""


def criteria_for(row: dict[str, Any]) -> dict[str, bool]:
    lic = (row.get("license_category") or "").lower()
    chain = (row.get("chain") or "").lower()
    vrm_ok = row.get("vrm_check_status") == "ok_vrm"
    license_ok = lic in ("green", "yellow")
    identity_ok = _has(row.get("name")) and (
        _has(row.get("contract")) or lic == "green" or chain in ("arweave",)
    )
    return {
        "vrm_ok": bool(vrm_ok),
        "license_ok": bool(license_ok),
        "identity_ok": bool(identity_ok),
        "banner_ok": _has(row.get("banner_image_url")),
        "pfp_ok": _has(row.get("image_url")) or _has(row.get("sample_nft_image")),
        "desc_ok": _has(row.get("description")),
        "social_ok": _has(row.get("twitter_username")) or _has(row.get("discord_url")),
        "count_ok": _has(row.get("total_supply")) or _has(row.get("avatar_count")),
    }


def score(row: dict[str, Any]) -> dict[str, Any]:
    crit = criteria_for(row)
    ready = all(crit[c] for c in CRITICAL)
    total = sum(1 for v in crit.values() if v)
    return {"ready": 1 if ready else 0, "score": total, "criteria": crit}


def _row_factory(cur: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {c[0]: row[idx] for idx, c in enumerate(cur.description)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score hubzz-ingress readiness per collection.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--tiers", default="A,B,C")
    ap.add_argument("--now", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    tiers = tuple(t.strip().upper() for t in args.tiers.split(",") if t.strip())
    stamp = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = sqlite3.connect(args.db)
    conn.row_factory = _row_factory  # type: ignore[assignment]
    ph = ",".join("?" for _ in tiers)
    rows = list(conn.execute(f"SELECT * FROM collections WHERE tier IN ({ph})", tiers))

    results = []
    ready_names, near_names = [], []
    for row in rows:
        s = score(row)
        results.append((row, s))
        if s["ready"]:
            ready_names.append(row["name"])
        elif s["score"] >= 6:
            missing = [c for c in CRITICAL if not s["criteria"][c]]
            near_names.append(f"{row['name']} (missing: {', '.join(missing)})")

    print(f"\n=== HUBZZ-INGRESS READINESS ({len(rows)} collections, tiers {','.join(tiers)}) ===", file=sys.stderr)
    print(f"READY (all critical met): {len(ready_names)}", file=sys.stderr)
    for n in ready_names:
        print(f"  ✅ {n}", file=sys.stderr)
    print(f"\nNEAR-READY (score>=6, missing a critical): {len(near_names)}", file=sys.stderr)
    for n in near_names[:20]:
        print(f"  🔸 {n}", file=sys.stderr)
    # Blocker analysis: which critical criterion fails most?
    from collections import Counter
    blockers = Counter()
    for _, s in results:
        for c in CRITICAL:
            if not s["criteria"][c]:
                blockers[c] += 1
    print(f"\ntop blockers: {dict(blockers)}", file=sys.stderr)

    if args.dry_run:
        print("\ndry-run: no DB writes", file=sys.stderr)
        conn.close()
        return 0

    for row, s in results:
        conn.execute(
            "UPDATE collections SET ready=?, readiness_score=?, readiness_criteria=?, readiness_at=? WHERE id=?",
            (s["ready"], s["score"], json.dumps(s["criteria"]), stamp, row["id"]),
        )
    conn.commit()
    conn.close()
    print(f"\nwrote readiness for {len(results)} collections", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
