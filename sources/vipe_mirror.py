"""Import the VIPE platform's curation from the altii.co mirror.

VIPE (vipe.io, now defunct) listed a curated set of 3D-avatar collections with a
taxonomy and setup notes this catalog had no equivalent for: a category, how the
collection ships 3D, a hand-written description, real marketing banner/pfp art,
and — for some — which metadata field holds the VRM.

The Hubzz/altii.co team reconstructed that listing from a Wayback mirror of
vipe.io (packages/avatars/lab/src/data/altiiData.ts in HubzzInc/pre-alpha). It is
vendored here as data/altii_vipe_mirror.json so this repo stands alone.

Matching is by contract (authoritative), then normalized name. Existing catalog
values are never overwritten — empty fields are filled, and VIPE-specific fields
land in their own columns (migration 018).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = _REPO_ROOT / "data" / "altii_vipe_mirror.json"


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _items_to_int(v: Any) -> int | None:
    if not isinstance(v, str):
        return None
    digits = v.replace(",", "").strip()
    return int(digits) if digits.isdigit() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import VIPE mirror curation into the catalog.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    doc = json.loads(Path(args.src).read_text(encoding="utf-8"))
    mirror = doc.get("collections", [])

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name, contract, description, banner_image_url, image_url, "
                        "total_supply FROM collections").fetchall()
    by_contract = {(r["contract"] or "").lower(): r for r in rows if r["contract"]}
    by_name = {_norm(r["name"]): r for r in rows}

    matched, unmatched, updates = 0, [], []
    for m in mirror:
        c = (m.get("contract") or "").lower()
        row = by_contract.get(c) or by_name.get(_norm(m.get("name")))
        if not row:
            unmatched.append(m.get("name"))
            continue
        matched += 1
        fills = {
            "vipe_category": m.get("category"),
            "vipe_assets_3d": m.get("assets3D"),
            "vipe_metadata_param": m.get("metadataParam"),
            "curated_description": m.get("description"),
            "vipe_listed": 1,
        }
        # Fill only where the catalog is empty — never clobber existing data.
        if not (row["banner_image_url"] or "").strip() and m.get("banner"):
            fills["banner_image_url"] = m["banner"]
        if not (row["image_url"] or "").strip() and m.get("pfp"):
            fills["image_url"] = m["pfp"]
        if not (row["description"] or "").strip() and m.get("description"):
            fills["description"] = m["description"]
        if row["total_supply"] is None:
            n = _items_to_int(m.get("items"))
            if n:
                fills["total_supply"] = n
        updates.append((row["id"], row["name"], fills))

    print(f"mirror collections: {len(mirror)} | matched to catalog: {matched}", file=sys.stderr)
    for cid, name, f in updates:
        extra = [k for k in ("banner_image_url", "image_url", "description", "total_supply") if k in f]
        print(f"  {name[:30]:30} cat={str(f.get('vipe_category'))[:20]:20} "
              f"3d={str(f.get('vipe_assets_3d'))[:16]:16} filled={extra}", file=sys.stderr)
    if unmatched:
        print(f"\n  not in catalog ({len(unmatched)}): {unmatched}", file=sys.stderr)

    if args.dry_run:
        print("dry-run: no DB writes", file=sys.stderr)
        conn.close()
        return 0

    for cid, _, f in updates:
        cols = ", ".join(f"{k}=?" for k in f)
        conn.execute(f"UPDATE collections SET {cols} WHERE id=?", (*f.values(), cid))
    conn.commit()
    conn.close()
    print(f"\nenriched {len(updates)} collections from the VIPE mirror", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
