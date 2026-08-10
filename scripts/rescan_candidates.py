"""Re-scan OpenSea candidates that an earlier pass wrote off as `no_vrm`.

Those verdicts came from a weaker pipeline: a shallower metadata scan and a
reachability checker that sent no User-Agent (so ipfs.io and Cloudflare-fronted
hosts 403'd it and live files looked dead). This re-runs each candidate through
the current pipeline:

    metadata_url -> scan_metadata (VRM pointer detection)
                 -> check_url (partial-GLB validation, UA + IPFS gateway fallback)

A hit is a genuinely NEW VRM collection the catalog does not have. Nothing is
promoted automatically — promotion adds a collection, which is a human gate
(L1). Hits are written back to `opensea_candidates` and printed for review.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discover_metadata_fields import scan_metadata  # noqa: E402
from scripts.discover_vrm_urls import fetch_metadata  # noqa: E402
from scripts.check_vrm_reachable import check_url  # noqa: E402


def _row_factory(cur: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {c[0]: row[idx] for idx, c in enumerate(cur.description)}


def rescan_one(cand: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = (cand.get("metadata_url") or "").strip()
    if not url:
        return {"status": "no_metadata_url"}
    try:
        meta = fetch_metadata(url, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return {"status": "metadata_error", "reason": str(e)[:60]}
    cands = scan_metadata(meta) if isinstance(meta, (dict, list)) else []
    if not cands:
        return {"status": "no_vrm_pointer"}
    for c in cands:
        u = c.get("url")
        if not u:
            continue
        res = check_url(u, timeout=timeout)
        if res["reachable"] == 1:
            return {"status": res["status"], "vrm_url": u, "check": res, "field": c.get("field")}
    first = cands[0].get("url")
    return {"status": "pointer_unreachable", "vrm_url": first, "field": cands[0].get("field")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Re-scan written-off OpenSea candidates for VRMs.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--status", default="no_vrm", help="candidate status to re-scan")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=18.0)
    ap.add_argument("--now", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    stamp = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(args.db)
    conn.row_factory = _row_factory  # type: ignore[assignment]
    rows = list(conn.execute("""
        SELECT oc.slug, oc.name, oc.chain, oc.contract, oc.metadata_url
        FROM opensea_candidates oc
        WHERE oc.status = ?
          AND oc.metadata_url IS NOT NULL AND oc.metadata_url != ''
          AND NOT EXISTS (SELECT 1 FROM collections c WHERE lower(c.contract) = lower(oc.contract))
        ORDER BY oc.slug
    """, (args.status,)))
    conn.close()
    if args.limit:
        rows = rows[:args.limit]

    print(f"re-scanning {len(rows)} '{args.status}' candidates not in the catalog…\n", file=sys.stderr)

    results, tallies = [], {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for cand, r in zip(rows, ex.map(lambda c: rescan_one(c, args.timeout), rows)):
            st = r["status"]
            tallies[st] = tallies.get(st, 0) + 1
            results.append((cand, r))
            if st in ("ok_vrm", "reachable_not_vrm"):
                kb = f" {r['check']['bytes']//1024}KB" if r.get("check", {}).get("bytes") else ""
                icon = "🟢" if st == "ok_vrm" else "🟡"
                print(f"  {icon} NEW {cand['name'][:28]:28} {st}{kb}  via '{r.get('field')}'  {r['vrm_url'][:46]}",
                      file=sys.stderr)

    print(f"\nsummary: {tallies}", file=sys.stderr)
    hits = [(c, r) for c, r in results if r["status"] in ("ok_vrm", "reachable_not_vrm")]
    print(f"NEW VRM collections found: {len(hits)}", file=sys.stderr)

    if args.dry_run or not hits:
        if args.dry_run:
            print("dry-run: no DB writes", file=sys.stderr)
        return 0

    conn = sqlite3.connect(args.db)
    for cand, r in hits:
        conn.execute(
            "UPDATE opensea_candidates SET status='vrm', vrm_url_https=?, vrm_param=COALESCE(vrm_param,?) "
            "WHERE slug=?",
            (r["vrm_url"], r.get("field"), cand["slug"]))
    conn.commit()
    conn.close()
    print(f"marked {len(hits)} candidate(s) as vrm (promotion to a collection remains a human gate)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
