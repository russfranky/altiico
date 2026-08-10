"""Mark which catalog collections are ALREADY in Hubzz.

The readiness scorecard is only useful if it surfaces sets that are NOT yet
onboarded. This reads the live Hubzz avatar DB (packages/avatars/api/avatars.db
in the pre-alpha checkout) and marks each catalog collection:

  onboarded  present in Hubzz and fully optimized/served  -> nothing to do
  partial    present but not fully optimized (or a junk row) -> needs finishing
  absent     not in Hubzz                                  -> the actionable set

Matching is by contract first (authoritative), then by normalized name/slug.
Read-only against the Hubzz DB — it never writes there.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HUBZZ_DB = "/Users/russ/pre-alpha/packages/avatars/api/avatars.db"

# Catalog collections that map onto a single Hubzz set with a different name.
ALIASES = {
    "100avatars-r1": "100avatars",
    "100avatars-r2": "100avatars",
    "100avatars-r3": "100avatars",
    "vipe-heroes": "vipe-heroes-genesis",
    "grifterssquaddies": "grifters-squaddies",
    "retrodogesnft": "retrodoges",
}


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_hubzz(db: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute("""
        SELECT c.slug, c.name, c.contract, c.avatar_count,
               COUNT(a.id) AS rows_n,
               SUM(CASE WHEN a.status='optimized' THEN 1 ELSE 0 END) AS optimized_n
        FROM collections c LEFT JOIN avatars a ON a.collection_id = c.id
        GROUP BY c.id
    """).fetchall()
    conn.close()
    return [{"slug": r[0], "name": r[1], "contract": (r[2] or "").lower(),
             "declared": r[3] or 0, "rows": r[4] or 0, "optimized": r[5] or 0} for r in rows]


def classify(h: dict[str, Any]) -> str:
    """onboarded only when there is real, fully-optimized content."""
    if h["rows"] > 0 and h["optimized"] >= h["rows"] and h["rows"] > 1:
        return "onboarded"
    return "partial"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sync 'already in Hubzz' status onto the catalog.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--hubzz-db", default=DEFAULT_HUBZZ_DB)
    ap.add_argument("--now", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not Path(args.hubzz_db).exists():
        print(f"error: Hubzz DB not found at {args.hubzz_db}", file=sys.stderr)
        return 1

    stamp = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hub = load_hubzz(args.hubzz_db)
    by_contract = {h["contract"]: h for h in hub if h["contract"]}
    by_name = {_norm(h["slug"]): h for h in hub}
    by_name.update({_norm(h["name"]): h for h in hub})

    conn = sqlite3.connect(args.db)
    cols = conn.execute("SELECT id, name, contract FROM collections").fetchall()

    updates, tally = [], {"onboarded": 0, "partial": 0, "absent": 0}
    for cid, name, contract in cols:
        h = None
        alias = ALIASES.get(cid)
        if alias:
            h = by_name.get(_norm(alias))
        if not h and contract:
            h = by_contract.get(contract.lower())
        if not h:
            h = by_name.get(_norm(cid)) or by_name.get(_norm(name))
        if h:
            status = classify(h)
            updates.append((status, h["slug"], h["optimized"], h["rows"], stamp, cid))
        else:
            status = "absent"
            updates.append((status, None, None, None, stamp, cid))
        tally[status] += 1

    print(f"Hubzz sets: {len(hub)} | catalog: {len(cols)}", file=sys.stderr)
    print(f"  onboarded: {tally['onboarded']}   partial: {tally['partial']}   absent: {tally['absent']}",
          file=sys.stderr)
    for status, slug, opt, rows, _, cid in updates:
        if status != "absent":
            print(f"  {status:10} {cid[:30]:30} -> hubzz:{slug} ({opt}/{rows} optimized)", file=sys.stderr)

    if args.dry_run:
        print("dry-run: no DB writes", file=sys.stderr)
        conn.close()
        return 0

    conn.executemany(
        """UPDATE collections SET hubzz_status=?, hubzz_slug=?, hubzz_optimized=?,
           hubzz_rows=?, hubzz_synced_at=? WHERE id=?""", updates)
    conn.commit()
    conn.close()
    print(f"synced Hubzz presence for {len(updates)} collections", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
