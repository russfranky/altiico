#!/usr/bin/env python3
"""Materialize deterministic short descriptions into the catalog database.

Manual/evidenced short descriptions win. For remaining collections, derive a
bounded human-readable summary from curated_description or description so the
public payload has a concrete short_description field rather than an audit-only
computed value.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vrm_index.db"


def short_description(value: object, max_chars: int = 180) -> str:
    import re

    if max_chars < 1:
        return ""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^[#>*\-\s]+", "", text).strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    cut = text[: max_chars + 1]
    sentence_ends = [
        match.end(1)
        for match in re.finditer(r"([.!?])(?:\s|$)", cut)
        if match.end(1) <= max_chars
    ]
    if sentence_ends:
        return cut[: sentence_ends[-1]].strip()

    word = cut.rfind(" ")
    if word < max_chars // 2:
        word = max_chars
    return cut[:word].rstrip(" ,;:-") + "…"


def run(db_path: Path, *, max_chars: int = 180) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(collections)")}
        if "short_description" not in columns:
            conn.execute("ALTER TABLE collections ADD COLUMN short_description TEXT")
        rows = conn.execute(
            """
            SELECT id,short_description,curated_description,description
            FROM collections ORDER BY id
            """
        ).fetchall()
        updated = 0
        already = 0
        missing_source = 0
        for collection_id, existing, curated, description in rows:
            if str(existing or "").strip():
                already += 1
                continue
            derived = short_description(curated or description, max_chars=max_chars)
            if not derived:
                missing_source += 1
                continue
            conn.execute(
                "UPDATE collections SET short_description=? WHERE id=?",
                (derived, collection_id),
            )
            updated += 1
        conn.commit()
    finally:
        conn.close()
    return {
        "collections": len(rows),
        "updated": updated,
        "alreadyPresent": already,
        "missingSourceDescription": missing_source,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--max-chars", type=int, default=180)
    args = parser.parse_args()
    result = run(args.db, max_chars=args.max_chars)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
