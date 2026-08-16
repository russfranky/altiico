#!/usr/bin/env python3
"""Materialize strict collection research into vrm_index.db.

The research overlay is the place for facts that cannot be safely inferred from
chain/API data alone: lifecycle state, historical/social links, exact launch
dates, IP-rights notes, access gating, and documented no-release states.

This script is intentionally conservative:
- positive values require evidence before they overwrite catalog fields;
- explicit negative states require evidence;
- license/IP terms never imply file-access gating;
- a research-only collection may be inserted only when an explicit identity
  object provides a stable id and name.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research.json"

ADDED_COLUMNS = {
    "short_description": "TEXT",
    "project_status": "TEXT",
    "storage_types": "TEXT",
    "vrm_inventory_state": "TEXT",
    "vrm_inventory_count": "INTEGER",
    "vrm_inventory_complete": "INTEGER",
    "file_access_mode": "TEXT",
    "file_access_requires_ownership": "INTEGER",
    "ip_rights_summary": "TEXT",
    "catalog_research_evidence": "TEXT",
    "catalog_research_updated_at": "TEXT",
}
CORE_FIELD_MAP = {
    "banner": "banner_image_url",
    "logo": "image_url",
    "launch_date": "release_date",
    "discord": "discord_url",
}
IDENTITY_FIELD_MAP = {
    "name": "name",
    "creator": "creator",
    "tier": "tier",
    "chain": "chain",
    "contract": "contract",
    "opensea_slug": "opensea_slug",
    "project_url": "project_url",
    "source": "source",
    "notes": "notes",
}
SOCIAL_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,30}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def has(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def evidence(field: Any) -> list[dict[str, Any]]:
    if not isinstance(field, dict):
        return []
    raw = field.get("evidence")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict) and row]


def researched(field: Any) -> bool:
    return isinstance(field, dict) and bool(evidence(field))


def value(field: Any) -> Any:
    if not isinstance(field, dict):
        return None
    return field.get("value")


def x_handle(field: Any) -> str:
    raw = str(value(field) or "").strip()
    if not raw:
        raw = str((field or {}).get("handle") or "").strip() if isinstance(field, dict) else ""
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urllib.parse.urlsplit(raw)
        parts = [p for p in parsed.path.split("/") if p]
        raw = parts[0] if parts else ""
    raw = raw.lstrip("@")
    return raw if SOCIAL_HANDLE_RE.match(raw) else ""


def load_research(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("collections"), dict):
        raise ValueError("catalog_research.json must contain a collections object")
    return data


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def ensure_schema(conn: sqlite3.Connection) -> None:
    cols = table_columns(conn, "collections")
    for name, sql_type in ADDED_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE collections ADD COLUMN {name} {sql_type}")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_research_evidence (
            collection_id TEXT NOT NULL,
            field TEXT NOT NULL,
            state TEXT,
            value_json TEXT,
            evidence_json TEXT NOT NULL,
            observed_at TEXT,
            PRIMARY KEY (collection_id, field),
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );
        CREATE INDEX IF NOT EXISTS idx_catalog_research_state
          ON catalog_research_evidence(field, state);
        """
    )


def insert_missing_collection(
    conn: sqlite3.Connection, collection_id: str, identity: dict[str, Any]
) -> bool:
    if conn.execute("SELECT 1 FROM collections WHERE id=?", (collection_id,)).fetchone():
        return False
    name = str(identity.get("name") or "").strip()
    if not name:
        raise ValueError(f"{collection_id}: research-only collection needs identity.name")
    available = table_columns(conn, "collections")
    row: dict[str, Any] = {"id": collection_id, "name": name}
    for research_key, db_key in IDENTITY_FIELD_MAP.items():
        if db_key in available and has(identity.get(research_key)):
            row[db_key] = identity[research_key]
    row.setdefault("source", "catalog-research")
    columns = list(row)
    conn.execute(
        f"INSERT INTO collections ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
        [row[c] for c in columns],
    )
    contract = str(identity.get("contract") or "").strip()
    chain = str(identity.get("chain") or "ethereum").strip()
    if contract and table_exists(conn, "contracts"):
        contract_cols = table_columns(conn, "contracts")
        payload = {
            "collection_id": collection_id,
            "address": contract,
            "chain": chain,
            "is_primary": 1,
        }
        payload = {k: v for k, v in payload.items() if k in contract_cols}
        cols = list(payload)
        conn.execute(
            f"INSERT OR REPLACE INTO contracts ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
            [payload[c] for c in cols],
        )
    return True


def store_evidence(
    conn: sqlite3.Connection,
    collection_id: str,
    field_name: str,
    field: dict[str, Any],
    observed_at: str,
) -> None:
    ev = evidence(field)
    if not ev:
        return
    state = str(field.get("state") or field.get("mode") or "present")
    raw_value = field.get("value")
    if raw_value is None and field_name == "vrm_inventory":
        raw_value = field.get("urls") or []
    conn.execute(
        """
        INSERT OR REPLACE INTO catalog_research_evidence
          (collection_id,field,state,value_json,evidence_json,observed_at)
        VALUES (?,?,?,?,?,?)
        """,
        (
            collection_id,
            field_name,
            state,
            json.dumps(raw_value, ensure_ascii=False),
            json.dumps(ev, ensure_ascii=False),
            observed_at,
        ),
    )


def avatar_urls(conn: sqlite3.Connection, collection_id: str) -> list[str]:
    if not table_exists(conn, "avatars"):
        return []
    cols = table_columns(conn, "avatars")
    if "model_file_url" not in cols:
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
    ]


def known_vrm_urls(
    conn: sqlite3.Connection, collection_id: str, research_row: dict[str, Any]
) -> list[str]:
    urls = avatar_urls(conn, collection_id)
    inv = research_row.get("vrm_inventory")
    if isinstance(inv, dict) and isinstance(inv.get("urls"), list):
        urls.extend(str(u).strip() for u in inv["urls"] if has(u))
    row = conn.execute(
        "SELECT vrm_url_https,vrm_url_pattern FROM collections WHERE id=?",
        (collection_id,),
    ).fetchone()
    if row:
        for raw in row:
            text = str(raw or "").strip()
            if not text:
                continue
            # Descriptive prose is not an inventory URL.
            if text.startswith(("http://", "https://", "ipfs://", "ar://")):
                urls.append(text)
    return sorted(set(urls))


def infer_storage(urls: list[str]) -> list[str]:
    out: set[str] = set()
    for raw in urls:
        lowered = raw.lower()
        if lowered.startswith("ipfs://") or "/ipfs/" in lowered:
            out.add("ipfs")
        elif lowered.startswith("ar://") or "arweave.net/" in lowered:
            out.add("arweave")
        elif lowered.startswith(("http://", "https://")):
            out.add("https")
        elif lowered.startswith(("ethereum:", "data:")):
            out.add("onchain")
    return sorted(out)


def int_or_none(value: Any) -> int | None:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return None
    return out if out >= 0 else None


def expected_count(conn: sqlite3.Connection, collection_id: str) -> int | None:
    cols = table_columns(conn, "collections")
    wanted = [c for c in ("avatar_count", "total_supply", "max_supply") if c in cols]
    if not wanted:
        return None
    row = conn.execute(
        f"SELECT {','.join(wanted)} FROM collections WHERE id=?", (collection_id,)
    ).fetchone()
    if not row:
        return None
    for raw in row:
        parsed = int_or_none(raw)
        if parsed and parsed > 0:
            return parsed
    return None


def inventory_state(
    conn: sqlite3.Connection,
    collection_id: str,
    urls: list[str],
    research_row: dict[str, Any],
) -> tuple[str, int]:
    inv = research_row.get("vrm_inventory")
    if isinstance(inv, dict) and evidence(inv):
        state = str(inv.get("state") or inv.get("coverage") or "").strip().lower()
        if state in {"not_shipped", "holder_gated", "unrecoverable", "complete"}:
            return state, 1
    expected = expected_count(conn, collection_id)
    if expected is not None and expected > 0 and len(urls) >= expected:
        return "complete", 1
    if urls:
        return "partial", 0
    return "unknown", 0


def public_access_from_avatars(conn: sqlite3.Connection, collection_id: str) -> bool:
    if not table_exists(conn, "avatars"):
        return False
    cols = table_columns(conn, "avatars")
    if not {"collection_id", "is_public"}.issubset(cols):
        return False
    row = conn.execute(
        """
        SELECT COUNT(*), SUM(CASE WHEN is_public=1 THEN 1 ELSE 0 END)
        FROM avatars WHERE collection_id=?
        """,
        (collection_id,),
    ).fetchone()
    return bool(row and int(row[0] or 0) > 0 and int(row[0]) == int(row[1] or 0))


def ip_rights_summary(
    conn: sqlite3.Connection, collection_id: str, research_row: dict[str, Any]
) -> str:
    field = research_row.get("ip_rights")
    if researched(field):
        return str(field.get("summary") or field.get("value") or "").strip()
    cols = table_columns(conn, "collections")
    wanted = [c for c in ("vrm_license", "commercial_use", "allowed_user", "redistribution") if c in cols]
    if not wanted:
        return ""
    row = conn.execute(
        f"SELECT {','.join(wanted)} FROM collections WHERE id=?", (collection_id,)
    ).fetchone()
    if not row:
        return ""
    facts = [str(v).strip() for v in row if has(v) and str(v).strip().lower() != "unknown"]
    return "; ".join(facts)


def materialize_collection(
    conn: sqlite3.Connection,
    collection_id: str,
    research_row: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    inserted = insert_missing_collection(
        conn, collection_id, research_row.get("identity") or {}
    )
    columns = table_columns(conn, "collections")
    updates: dict[str, Any] = {}

    identity = research_row.get("identity") or {}
    for research_key, db_key in IDENTITY_FIELD_MAP.items():
        if db_key in columns and has(identity.get(research_key)):
            updates[db_key] = identity[research_key]

    for research_key, db_key in CORE_FIELD_MAP.items():
        field = research_row.get(research_key)
        if researched(field) and has(value(field)) and db_key in columns:
            updates[db_key] = value(field)

    x_field = research_row.get("x")
    handle = x_handle(x_field)
    if researched(x_field) and handle and "twitter_username" in columns:
        updates["twitter_username"] = handle

    short = research_row.get("short_description")
    if researched(short) and has(value(short)):
        updates["short_description"] = str(value(short)).strip()

    status = research_row.get("project_status")
    if researched(status):
        updates["project_status"] = str(value(status) or status.get("state") or "").lower()

    urls = known_vrm_urls(conn, collection_id, research_row)
    storage = research_row.get("storage")
    storage_value: Any = None
    if researched(storage) and has(value(storage)):
        storage_value = value(storage)
    else:
        storage_value = infer_storage(urls)
    if isinstance(storage_value, str):
        storage_value = [storage_value]
    updates["storage_types"] = json.dumps(storage_value or [], ensure_ascii=False)

    inv_state, inv_complete = inventory_state(conn, collection_id, urls, research_row)
    updates["vrm_inventory_state"] = inv_state
    updates["vrm_inventory_count"] = len(urls)
    updates["vrm_inventory_complete"] = inv_complete

    access = research_row.get("file_access")
    if researched(access):
        mode = str(access.get("mode") or value(access) or "").lower()
        updates["file_access_mode"] = mode or None
        ownership = access.get("requires_ownership")
        if ownership is not None:
            updates["file_access_requires_ownership"] = 1 if bool(ownership) else 0
    elif public_access_from_avatars(conn, collection_id) and inv_state == "complete":
        updates["file_access_mode"] = "public"
        updates["file_access_requires_ownership"] = 0

    rights = ip_rights_summary(conn, collection_id, research_row)
    if rights:
        updates["ip_rights_summary"] = rights

    evidence_payload: dict[str, Any] = {}
    for field_name, field in research_row.items():
        if field_name == "identity" or not isinstance(field, dict):
            continue
        if evidence(field):
            evidence_payload[field_name] = {
                "state": field.get("state") or field.get("mode") or "present",
                "value": field.get("value"),
                "evidence": evidence(field),
            }
            store_evidence(conn, collection_id, field_name, field, observed_at)
    updates["catalog_research_evidence"] = json.dumps(evidence_payload, ensure_ascii=False)
    updates["catalog_research_updated_at"] = observed_at

    if updates:
        keys = [k for k in updates if k in columns]
        conn.execute(
            f"UPDATE collections SET {','.join(f'{k}=?' for k in keys)} WHERE id=?",
            [updates[k] for k in keys] + [collection_id],
        )

    return {
        "id": collection_id,
        "inserted": inserted,
        "updatedFields": sorted(k for k in updates if k in columns),
        "vrmUrls": len(urls),
        "inventoryState": inv_state,
    }


def run(db_path: Path, research_path: Path) -> dict[str, Any]:
    data = load_research(research_path)
    observed_at = now_iso()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        ensure_schema(conn)
        results = []
        for collection_id, research_row in sorted((data.get("collections") or {}).items()):
            if not isinstance(research_row, dict):
                continue
            results.append(
                materialize_collection(conn, str(collection_id), research_row, observed_at)
            )
        conn.commit()
    finally:
        conn.close()
    return {
        "schema": "vrm-catalog-research-materialization-v1",
        "generatedAt": observed_at,
        "collections": len(results),
        "inserted": sum(1 for r in results if r["inserted"]),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    args = parser.parse_args()
    result = run(args.db, args.research)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
