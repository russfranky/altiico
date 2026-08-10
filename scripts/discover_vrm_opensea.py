"""Discover VRM URLs via the OpenSea /nfts endpoint (complements the on-chain path).

scripts/discover_vrm_urls.py resolves tokenURI over public RPC. That fails when a
contract does not implement tokenURI, is non-standard, or the RPC balks
(no_tokenuri / metadata_error). OpenSea already indexed those tokens, so this
path asks OpenSea for real token rows, then reuses the same
scan_metadata -> check_url pipeline to find and validate a VRM.

Requires a working OpenSea API key at ~/.opensea/api_key with access to
GET /collection/{slug}/nfts (the official key has it).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discover_metadata_fields import scan_metadata  # noqa: E402
from scripts.check_vrm_reachable import check_url  # noqa: E402
from scripts.discover_vrm_urls import fetch_metadata  # noqa: E402

API = "https://api.opensea.io/api/v2"
KEY_PATH = Path.home() / ".opensea" / "api_key"


def _key() -> str:
    return KEY_PATH.read_text().strip()


def _get(url: str, timeout: float = 25.0) -> Any:
    req = urllib.request.Request(url, headers={
        "X-API-KEY": _key(), "Accept": "application/json", "User-Agent": "vrm-catalog/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return json.load(r)


def collection_nfts(slug: str, limit: int = 20, timeout: float = 25.0) -> list[dict[str, Any]]:
    data = _get(f"{API}/collection/{slug}/nfts?limit={limit}", timeout=timeout)
    return data.get("nfts", []) or []


def _row_factory(cur: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {c[0]: row[idx] for idx, c in enumerate(cur.description)}


def discover_one(slug: str, sample: int, timeout: float) -> dict[str, Any]:
    try:
        nfts = collection_nfts(slug, limit=sample, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return {"status": "opensea_error", "reason": str(e)[:70]}
    if not nfts:
        return {"status": "no_nfts"}

    for n in nfts:
        # 1. A direct animation_url that looks like a VRM.
        anim = n.get("animation_url") or ""
        if anim and ".vrm" in anim.lower():
            res = check_url(anim, timeout=timeout)
            if res["reachable"] == 1:
                return {"status": res["status"], "vrm_url": anim, "check": res, "via": "animation_url"}
        # 2. Follow metadata_url (may be an inline data: URI) and scan it.
        murl = n.get("metadata_url")
        if not murl:
            continue
        try:
            meta = fetch_metadata(murl, timeout=timeout)
        except Exception:  # noqa: BLE001
            continue
        cands = scan_metadata(meta) if isinstance(meta, (dict, list)) else []
        for c in cands:
            u = c.get("url")
            if not u:
                continue
            res = check_url(u, timeout=timeout)
            if res["reachable"] == 1:
                return {"status": res["status"], "vrm_url": u, "check": res, "via": "metadata_url"}
            # remember the first unreachable pointer as a fallback report
            if "first_dead" not in locals():
                first_dead = (u, res)  # noqa: F841
    fd = locals().get("first_dead")
    if fd:
        return {"status": "vrm_pointer_unreachable", "vrm_url": fd[0], "check": fd[1], "via": "metadata_url"}
    return {"status": "no_vrm_pointer"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Discover VRM URLs via OpenSea /nfts.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--where", default="(vrm_check_status IN ('no_url','no_tokenuri','metadata_error','no_vrm_pointer') OR vrm_check_status IS NULL)")
    ap.add_argument("--tiers", default="A,B,C")
    ap.add_argument("--sample", type=int, default=12, help="tokens to sample per collection")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=22.0)
    ap.add_argument("--now", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not KEY_PATH.exists():
        print(f"error: no OpenSea key at {KEY_PATH}", file=sys.stderr)
        return 1

    tiers = tuple(t.strip().upper() for t in args.tiers.split(",") if t.strip())
    stamp = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = sqlite3.connect(args.db)
    conn.row_factory = _row_factory  # type: ignore[assignment]
    ph = ",".join("?" for _ in tiers)
    rows = list(conn.execute(
        f"""SELECT id,name,opensea_slug,vrm_check_status FROM collections
            WHERE tier IN ({ph}) AND ({args.where})
              AND opensea_slug IS NOT NULL AND opensea_slug!='' AND opensea_slug NOT LIKE 'unidentified%'
            ORDER BY name""", tiers))
    conn.close()
    if args.limit:
        rows = rows[:args.limit]

    print(f"OpenSea discovery over {len(rows)} collections (sample={args.sample})…\n", file=sys.stderr)
    found, tallies = [], {}
    for row in rows:
        r = discover_one(row["opensea_slug"], args.sample, args.timeout)
        st = r["status"]
        tallies[st] = tallies.get(st, 0) + 1
        icon = {"ok_vrm": "🟢", "reachable_not_vrm": "🟡", "vrm_pointer_unreachable": "🔎"}.get(st, "·")
        extra = f"  {r['vrm_url'][:52]} (via {r.get('via')})" if r.get("vrm_url") else ""
        print(f"  {icon} {row['name'][:30]:30} {st}{extra}", file=sys.stderr)
        if r.get("vrm_url") and r.get("check") and row.get("vrm_check_status") != "ok_vrm":
            found.append((row, r))

    print(f"\nsummary: {tallies}", file=sys.stderr)
    print(f"pointers discovered: {len(found)}", file=sys.stderr)

    if args.dry_run or not found:
        if args.dry_run:
            print("dry-run: no DB writes", file=sys.stderr)
        return 0

    conn = sqlite3.connect(args.db)
    try:
        for row, r in found:
            chk = r["check"]
            conn.execute(
                """UPDATE collections SET vrm_url_https=?, vrm_reachable=?, vrm_check_status=?,
                   vrm_check_http=?, vrm_check_bytes=?, vrm_check_url=?, vrm_checked_at=? WHERE id=?""",
                (r["vrm_url"], chk["reachable"], chk["status"], chk["http"], chk["bytes"],
                 chk["used_url"], stamp, row["id"]))
        conn.commit()
    finally:
        conn.close()
    print(f"wrote {len(found)} discovered VRM URLs", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
