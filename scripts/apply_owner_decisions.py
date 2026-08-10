"""Apply data/owner_decisions.yaml onto the catalog.

The owner's call outranks the scorecard: an `exclude` collection is never
presented as an onboarding candidate again, however well it scores.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
VALID = {"exclude", "include", "defer"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Apply owner decisions to the catalog.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--file", default=str(_REPO_ROOT / "data" / "owner_decisions.yaml"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"no decisions file at {path} — nothing to apply", file=sys.stderr)
        return 0
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    decisions = doc.get("decisions") or []

    conn = sqlite3.connect(args.db)
    applied, missing, bad = 0, [], []
    for d in decisions:
        cid, dec = d.get("id"), (d.get("decision") or "").strip()
        if dec not in VALID:
            bad.append((cid, dec)); continue
        row = conn.execute("SELECT 1 FROM collections WHERE id=?", (cid,)).fetchone()
        if not row:
            missing.append(cid); continue
        if not args.dry_run:
            conn.execute("UPDATE collections SET owner_decision=?, owner_decision_reason=? WHERE id=?",
                         (dec, d.get("reason"), cid))
        applied += 1
        print(f"  {dec:8} {cid}", file=sys.stderr)

    # Clear decisions that were removed from the YAML.
    if not args.dry_run:
        ids = [d.get("id") for d in decisions if (d.get("decision") or "") in VALID]
        ph = ",".join("?" for _ in ids) or "''"
        conn.execute(f"UPDATE collections SET owner_decision=NULL, owner_decision_reason=NULL "
                     f"WHERE owner_decision IS NOT NULL AND id NOT IN ({ph})", ids)
        conn.commit()
    conn.close()

    if missing: print(f"  WARNING unknown collection id(s): {missing}", file=sys.stderr)
    if bad:     print(f"  WARNING invalid decision(s): {bad}", file=sys.stderr)
    print(f"applied {applied} owner decision(s)" + (" (dry-run)" if args.dry_run else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
