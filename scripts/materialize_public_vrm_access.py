#!/usr/bin/env python3
"""Materialize public VRM file access from successful unauthenticated probes.

The structural inventory probe performs plain unauthenticated network requests.
When a non-terminal collection has an exhaustive inventory and every URL probes
as a VRM, that is direct evidence that owning the NFT is not required merely to
fetch the file.

Existing explicit holder/account-gated research always wins; this script only
fills unknown access fields.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_INVENTORY = ROOT / "static" / "data" / "vrm-inventory.json"
DEFAULT_PROBE = ROOT / "data" / "vrm_inventory_probe.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_schema(conn: sqlite3.Connection) -> None:
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(collections)")}
    if "file_access_mode" not in cols:
        conn.execute("ALTER TABLE collections ADD COLUMN file_access_mode TEXT")
    if "file_access_requires_ownership" not in cols:
        conn.execute(
            "ALTER TABLE collections ADD COLUMN file_access_requires_ownership INTEGER"
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_research_evidence (
            collection_id TEXT NOT NULL,
            field TEXT NOT NULL,
            state TEXT,
            value_json TEXT,
            evidence_json TEXT NOT NULL,
            observed_at TEXT,
            PRIMARY KEY (collection_id, field)
        )
        """
    )


def run(db_path: Path, inventory_path: Path, probe_path: Path) -> dict[str, int]:
    inventory = {
        str(row.get("collection_id")): row
        for row in load(inventory_path).get("collections") or []
        if isinstance(row, dict) and row.get("collection_id")
    }
    probes = {
        str(row.get("catalogId")): row
        for row in load(probe_path).get("collections") or []
        if isinstance(row, dict) and row.get("catalogId")
    }
    observed_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema(conn)
        updated = 0
        already_resolved = 0
        not_proven_public = 0
        for collection_id, inv in inventory.items():
            row = conn.execute(
                """
                SELECT file_access_mode,file_access_requires_ownership
                FROM collections WHERE id=?
                """,
                (collection_id,),
            ).fetchone()
            if row is None:
                continue
            existing_mode = str(row[0] or "").strip().lower()
            if existing_mode in {"public", "holder_gated", "account_gated", "unavailable"}:
                already_resolved += 1
                continue

            probe = probes.get(collection_id) or {}
            if (
                str(inv.get("state") or "").lower() != "complete"
                or not inv.get("urls")
                or not probe.get("structurallyComplete")
                or int(probe.get("validVrmUrls") or 0) != len(inv.get("urls") or [])
            ):
                not_proven_public += 1
                continue

            conn.execute(
                """
                UPDATE collections
                SET file_access_mode='public', file_access_requires_ownership=0
                WHERE id=?
                """,
                (collection_id,),
            )
            evidence = [
                {
                    "kind": "unauthenticated_structural_vrm_probe",
                    "source": str(probe_path),
                    "observed_at": observed_at,
                    "urls": int(probe.get("validVrmUrls") or 0),
                    "note": "Every exhaustive inventory URL resolved without credentials and contained VRM/VRMC_vrm.",
                }
            ]
            conn.execute(
                """
                INSERT OR REPLACE INTO catalog_research_evidence
                  (collection_id,field,state,value_json,evidence_json,observed_at)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    collection_id,
                    "file_access",
                    "public",
                    json.dumps(
                        {"mode": "public", "requires_ownership": False},
                        ensure_ascii=False,
                    ),
                    json.dumps(evidence, ensure_ascii=False),
                    observed_at,
                ),
            )
            updated += 1
        conn.commit()
    finally:
        conn.close()

    return {
        "collections": len(inventory),
        "updatedPublic": updated,
        "alreadyResolved": already_resolved,
        "notProvenPublic": not_proven_public,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    args = parser.parse_args()
    result = run(args.db, args.inventory, args.probe)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
