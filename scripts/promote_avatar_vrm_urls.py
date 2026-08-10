"""Promote a per-avatar VRM URL to its collection when the collection has none.

The `avatars` table (imported from the Open Source Avatars registry) carries
`model_file_url` — a direct, working VRM link — for thousands of avatars. Yet
several collections were still marked `no_url` at the collection level, because
the discovery paths only looked on-chain / at OpenSea. This closes that gap
using data already in the DB: pick a candidate avatar URL, validate it with the
partial-GLB reachability check, and write the winner to the collection.

Never downgrades a collection that already has a confirmed-live VRM.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.check_vrm_reachable import check_url  # noqa: E402


def _row_factory(cur: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {c[0]: row[idx] for idx, c in enumerate(cur.description)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Promote avatar model_file_url to the collection.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--tries", type=int, default=3, help="candidate avatars to test per collection")
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("--now", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    stamp = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(args.db)
    conn.row_factory = _row_factory  # type: ignore[assignment]

    targets = list(conn.execute("""
        SELECT c.id, c.name, c.vrm_check_status
        FROM collections c
        WHERE (c.vrm_check_status IS NULL OR c.vrm_check_status != 'ok_vrm')
          AND EXISTS (SELECT 1 FROM avatars a
                      WHERE a.collection_id = c.id
                        AND a.model_file_url IS NOT NULL AND a.model_file_url != '')
        ORDER BY c.name
    """))
    print(f"{len(targets)} collection(s) with avatar VRM URLs but no confirmed collection VRM\n", file=sys.stderr)

    found = []
    for t in targets:
        cands = [r["model_file_url"] for r in conn.execute(
            "SELECT DISTINCT model_file_url FROM avatars WHERE collection_id=? "
            "AND model_file_url IS NOT NULL AND model_file_url!='' LIMIT ?",
            (t["id"], args.tries))]
        hit = None
        for u in cands:
            res = check_url(u, timeout=args.timeout)
            if res["reachable"] == 1:
                hit = (u, res)
                break
        if hit:
            icon = "🟢" if hit[1]["status"] == "ok_vrm" else "🟡"
            kb = f" {hit[1]['bytes']//1024}KB" if hit[1].get("bytes") else ""
            print(f"  {icon} {t['name'][:32]:32} {hit[1]['status']}{kb}  {hit[0][:56]}", file=sys.stderr)
            found.append((t, hit))
        else:
            print(f"  ·  {t['name'][:32]:32} no reachable avatar URL ({len(cands)} tried)", file=sys.stderr)

    print(f"\npromotable: {len(found)}", file=sys.stderr)
    if args.dry_run or not found:
        if args.dry_run:
            print("dry-run: no DB writes", file=sys.stderr)
        conn.close()
        return 0

    for t, (url, res) in found:
        conn.execute(
            """UPDATE collections SET vrm_url_https=?, vrm_reachable=?, vrm_check_status=?,
               vrm_check_http=?, vrm_check_bytes=?, vrm_check_url=?, vrm_checked_at=? WHERE id=?""",
            (url, res["reachable"], res["status"], res["http"], res["bytes"],
             res["used_url"], stamp, t["id"]))
    conn.commit()
    conn.close()
    print(f"promoted {len(found)} VRM URL(s) to collection level", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
