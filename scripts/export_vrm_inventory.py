#!/usr/bin/env python3
"""Export per-collection VRM inventory and access/storage evidence.

A collection inventory is not considered complete merely because one sample VRM
was found. Complete means one of:
- all expected model URLs are enumerated;
- an evidenced authoritative URL template covers the collection; or
- research establishes a terminal state such as not_shipped/holder_gated where
  public per-token links do not exist.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research.json"
DEFAULT_OUTPUT = ROOT / "static" / "data" / "vrm-inventory.json"
TOKEN_TEMPLATE_RE = re.compile(r"(?:\{(?:token_id|tokenId|id|token)\}|%d)", re.I)
URL_PREFIXES = ("http://", "https://", "ipfs://", "ar://")
TERMINAL_RESEARCH_STATES = {"not_shipped", "holder_gated", "unrecoverable"}


def has(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def load_research(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"collections": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data.get("collections"), dict) else {"collections": {}}


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({name})")}


def valid_url(raw: Any) -> bool:
    text = str(raw or "").strip()
    return bool(text and text.startswith(URL_PREFIXES) and not any(ch.isspace() for ch in text))


def storage(urls: list[str]) -> list[str]:
    providers: set[str] = set()
    for raw in urls:
        url = raw.lower()
        if url.startswith("ipfs://") or "/ipfs/" in url:
            providers.add("ipfs")
        elif url.startswith("ar://") or "arweave.net/" in url:
            providers.add("arweave")
        elif url.startswith(("http://", "https://")):
            providers.add("https")
        elif url.startswith(("ethereum:", "data:")):
            providers.add("onchain")
    return sorted(providers)


def evidence(field: Any) -> list[dict[str, Any]]:
    if not isinstance(field, dict) or not isinstance(field.get("evidence"), list):
        return []
    return [row for row in field["evidence"] if isinstance(row, dict) and row]


def expected(row: dict[str, Any]) -> int | None:
    for key in ("avatar_count", "total_supply", "max_supply"):
        try:
            value = int(row.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def avatar_urls(conn: sqlite3.Connection, collection_id: str) -> list[str]:
    if not table_exists(conn, "avatars"):
        return []
    cols = table_columns(conn, "avatars")
    if not {"collection_id", "model_file_url"}.issubset(cols):
        return []
    return [
        str(row[0]).strip()
        for row in conn.execute(
            """
            SELECT DISTINCT model_file_url FROM avatars
            WHERE collection_id=? AND TRIM(COALESCE(model_file_url,''))<>''
            ORDER BY model_file_url
            """,
            (collection_id,),
        ).fetchall()
        if valid_url(row[0])
    ]


def research_urls(research_row: dict[str, Any]) -> list[str]:
    inv = research_row.get("vrm_inventory")
    if not isinstance(inv, dict) or not isinstance(inv.get("urls"), list):
        return []
    return [str(url).strip() for url in inv["urls"] if valid_url(url)]


def inventory_for(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    research_row: dict[str, Any],
) -> dict[str, Any]:
    collection_id = str(row["id"])
    urls = avatar_urls(conn, collection_id) + research_urls(research_row)
    direct = str(row.get("vrm_url_https") or "").strip()
    if valid_url(direct):
        urls.append(direct)
    urls = sorted(set(urls))

    raw_template = str(row.get("vrm_url_pattern") or "").strip()
    template = raw_template if valid_url(raw_template) and TOKEN_TEMPLATE_RE.search(raw_template) else None
    inv_override = research_row.get("vrm_inventory")
    if isinstance(inv_override, dict):
        candidate_template = str(inv_override.get("url_template") or "").strip()
        if valid_url(candidate_template) and TOKEN_TEMPLATE_RE.search(candidate_template):
            template = candidate_template

    expected_count = expected(row)
    state = "unknown"
    complete = False
    terminal = False
    if isinstance(inv_override, dict) and evidence(inv_override):
        observed_state = str(
            inv_override.get("state") or inv_override.get("coverage") or ""
        ).strip().lower()
        if observed_state in TERMINAL_RESEARCH_STATES:
            state = observed_state
            complete = True
            terminal = True
        elif observed_state == "complete":
            state = "complete"
            complete = True

    if not complete and template and expected_count:
        state = "complete_template"
        complete = True
    elif not complete and expected_count and len(urls) >= expected_count:
        state = "complete"
        complete = True
    elif not complete and urls:
        state = "partial"

    access = research_row.get("file_access")
    access_mode = None
    requires_ownership = None
    access_evidence: list[dict[str, Any]] = []
    if isinstance(access, dict) and evidence(access):
        access_mode = str(access.get("mode") or access.get("value") or "").strip().lower() or None
        requires_ownership = access.get("requires_ownership")
        access_evidence = evidence(access)
    elif "file_access_mode" in row and has(row.get("file_access_mode")):
        access_mode = str(row["file_access_mode"])
        raw = row.get("file_access_requires_ownership")
        requires_ownership = None if raw is None else bool(raw)

    storage_override = research_row.get("storage")
    storage_types = storage(urls + ([template] if template else []))
    storage_evidence: list[dict[str, Any]] = []
    storage_scope = "vrm_files"
    if isinstance(storage_override, dict) and evidence(storage_override):
        raw_value = storage_override.get("value")
        if isinstance(raw_value, list):
            storage_types = sorted({str(v) for v in raw_value if has(v)})
        elif has(raw_value):
            storage_types = [str(raw_value)]
        storage_evidence = evidence(storage_override)
        storage_scope = str(storage_override.get("scope") or storage_scope)

    return {
        "collection_id": collection_id,
        "name": row.get("name"),
        "state": state,
        "complete": complete,
        "terminal": terminal,
        "expected_models": expected_count,
        "enumerated_urls": len(urls),
        "urls": urls,
        "url_template": template,
        "storage": {"types": storage_types, "scope": storage_scope, "evidence": storage_evidence},
        "access": {
            "mode": access_mode,
            "requires_ownership": requires_ownership,
            "evidence": access_evidence,
        },
        "inventory_evidence": evidence(inv_override),
    }


def run(db_path: Path, research_path: Path, output_path: Path) -> dict[str, Any]:
    research = load_research(research_path).get("collections") or {}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM collections ORDER BY name")]
        inventories = [
            inventory_for(conn, row, research.get(str(row["id"])) or {}) for row in rows
        ]
    finally:
        conn.close()

    payload = {
        "schema": "vrm-catalog-inventory-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "policy": (
            "Complete inventory means exhaustive model URLs, an authoritative tokenized URL "
            "template, or an evidenced terminal state; one sample URL never implies completeness."
        ),
        "summary": {
            "collections": len(inventories),
            "complete": sum(1 for row in inventories if row["complete"]),
            "partial": sum(1 for row in inventories if row["state"] == "partial"),
            "unknown": sum(1 for row in inventories if row["state"] == "unknown"),
            "notShipped": sum(1 for row in inventories if row["state"] == "not_shipped"),
            "holderGated": sum(1 for row in inventories if row["state"] == "holder_gated"),
            "enumeratedUrls": sum(int(row["enumerated_urls"]) for row in inventories),
        },
        "collections": inventories,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    payload = run(args.db, args.research, args.output)
    print(json.dumps(payload["summary"], indent=2))
    if args.strict and (payload["summary"]["partial"] or payload["summary"]["unknown"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
