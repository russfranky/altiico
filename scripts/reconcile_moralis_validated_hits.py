#!/usr/bin/env python3
"""Reconcile binary-proven Moralis hits into already-identified catalog records.

This is intentionally narrow. It never creates collections and never matches by
name. A hit must target an existing catalog ID whose chain+contract identity
matches the validation report. Only rows with complete VRM binary proof are
materialized into collection/avatar VRM fields and provenance tables.
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
DEFAULT_REPORT = ROOT / "data" / "moralis_candidate_validation.json"
DEFAULT_OUT = ROOT / "data" / "moralis_candidate_reconciliation.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
CONTRACT_RE = re.compile(r"^0x[0-9a-f]{40}$", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def complete_proof(hit: dict[str, Any]) -> bool:
    return bool(
        hit.get("status") == "valid_vrm"
        and hit.get("vrm_spec") in {"0.x", "1.0"}
        and SHA256_RE.fullmatch(str(hit.get("sha256") or ""))
        and str(hit.get("canonical_url") or "").strip()
        and int(hit.get("byte_length") or 0) > 0
    )


def identity_matches(conn: sqlite3.Connection, hit: dict[str, Any]) -> tuple[bool, str]:
    catalog_id = str(hit.get("catalogId") or "").strip()
    chain = str(hit.get("chain") or "").strip().lower()
    contract = str(hit.get("contract") or "").strip().lower()
    if not catalog_id or not chain or not CONTRACT_RE.fullmatch(contract):
        return False, "incomplete_hit_identity"
    row = conn.execute(
        "SELECT id, chain, contract FROM collections WHERE id=?", (catalog_id,)
    ).fetchone()
    if row is None:
        return False, "collection_not_found"
    if str(row["chain"] or "").lower() != chain:
        return False, "chain_mismatch"
    direct = str(row["contract"] or "").lower()
    if direct == contract:
        return True, "collection_primary_contract"
    if table_exists(conn, "contracts"):
        found = conn.execute(
            "SELECT 1 FROM contracts WHERE collection_id=? AND lower(address)=? AND lower(chain)=?",
            (catalog_id, contract, chain),
        ).fetchone()
        if found:
            return True, "collection_contract_table"
    return False, "contract_mismatch"


def avatar_id(hit: dict[str, Any]) -> str:
    token_id = str(hit.get("tokenId") or "").strip()
    if not token_id:
        raise ValueError("validated hit is missing tokenId")
    return f"{hit['catalogId']}:{token_id}"


def upsert_dynamic(
    conn: sqlite3.Connection,
    table: str,
    values: dict[str, Any],
    conflict_column: str,
    *,
    protected_columns: set[str] | None = None,
) -> None:
    available = columns(conn, table)
    clean = {key: value for key, value in values.items() if key in available}
    if conflict_column not in clean:
        raise RuntimeError(f"{table} lacks required conflict column {conflict_column}")
    protected = protected_columns or {conflict_column}
    update_names = [key for key in clean if key not in protected]
    names = list(clean)
    sql = (
        f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})"
    )
    if update_names:
        sql += " ON CONFLICT(" + conflict_column + ") DO UPDATE SET " + ", ".join(
            f"{name}=excluded.{name}" for name in update_names
        )
    else:
        sql += f" ON CONFLICT({conflict_column}) DO NOTHING"
    conn.execute(sql, tuple(clean[name] for name in names))


def reconcile_hit(
    conn: sqlite3.Connection, hit: dict[str, Any], stamp: str
) -> dict[str, Any]:
    if not complete_proof(hit):
        raise ValueError("hit lacks complete binary VRM proof")
    ok, identity_mode = identity_matches(conn, hit)
    if not ok:
        raise ValueError(f"identity rejected: {identity_mode}")

    aid = avatar_id(hit)
    canonical = str(hit["canonical_url"])
    transport = str(hit.get("transport_url") or canonical)
    existing_avatar = conn.execute(
        "SELECT * FROM avatars WHERE id=?", (aid,)
    ).fetchone()
    if existing_avatar is not None:
        if str(existing_avatar["collection_id"] or "") != str(hit["catalogId"]):
            raise ValueError(f"avatar id collision for {aid}")
        prior_url = str(existing_avatar["model_file_url"] or "").strip()
        if prior_url and prior_url not in {canonical, transport}:
            raise ValueError(f"avatar {aid} already has a different model URL")

    metadata = {
        "token_id": str(hit.get("tokenId")),
        "token_uri": hit.get("tokenUri"),
        "source": "moralis_model_discovery",
        "source_path": hit.get("sourcePath"),
        "chain": hit.get("chain"),
        "contract": hit.get("contract"),
        "binary_validation": {
            "canonical_url": canonical,
            "transport_url": transport,
            "vrm_spec": hit.get("vrm_spec"),
            "content_sha256": hit.get("sha256"),
            "json_chunk_sha256": hit.get("json_chunk_sha256"),
            "byte_length": hit.get("byte_length"),
            "observed_at": hit.get("observedAt") or stamp,
        },
    }
    avatar_values = {
        "id": aid,
        "collection_id": hit["catalogId"],
        "name": f"{hit.get('name') or hit['catalogId']} #{hit.get('tokenId')}",
        "model_file_url": transport,
        "format": "vrm",
        "is_public": 1,
        "metadata_json": json.dumps(metadata, separators=(",", ":")),
        "reachable": 1,
        "check_status": "ok_vrm",
        "checked_at": hit.get("observedAt") or stamp,
    }
    upsert_dynamic(
        conn,
        "avatars",
        avatar_values,
        "id",
        protected_columns={"id", "collection_id"},
    )

    vrm_values = {
        "source_url": canonical,
        "extracted_at": hit.get("observedAt") or stamp,
        "extractor_version": "moralis-candidate-binary-validation-v1",
        "vrm_spec": hit.get("vrm_spec"),
        "vrm_meta_json": None,
        "parse_error": None,
        "content_length": int(hit["byte_length"]),
        "content_sha256": hit.get("sha256"),
        "json_chunk_sha256": hit.get("json_chunk_sha256"),
        "observed_content_length": int(hit["byte_length"]),
        "transport_url": transport,
    }
    upsert_dynamic(conn, "vrm_metadata", vrm_values, "source_url")
    upsert_dynamic(
        conn,
        "avatar_vrm",
        {"avatar_id": aid, "vrm_source_url": canonical},
        "avatar_id",
    )

    collection = conn.execute(
        "SELECT * FROM collections WHERE id=?", (hit["catalogId"],)
    ).fetchone()
    collection_cols = columns(conn, "collections")
    existing_confirmed = (
        "vrm_check_status" in collection_cols
        and collection["vrm_check_status"] == "ok_vrm"
        and bool(collection["vrm_url_https"] if "vrm_url_https" in collection_cols else None)
    )
    collection_updated = False
    if not existing_confirmed:
        updates = {
            "vrm_url_https": transport,
            "vrm_reachable": 1,
            "vrm_check_status": "ok_vrm",
            "vrm_check_bytes": int(hit["byte_length"]),
            "vrm_check_url": transport,
            "vrm_checked_at": hit.get("observedAt") or stamp,
        }
        clean = {key: value for key, value in updates.items() if key in collection_cols}
        if clean:
            conn.execute(
                f"UPDATE collections SET {', '.join(f'{key}=?' for key in clean)} WHERE id=?",
                (*clean.values(), hit["catalogId"]),
            )
            collection_updated = True

    if table_exists(conn, "promotion_candidates"):
        conn.execute(
            """
            UPDATE promotion_candidates
            SET promotion_state='reconciled',
                reason='binary proof reconciled into existing exact collection identity'
            WHERE collection_id=? AND canonical_url=? AND sha256=?
              AND promotion_state='ready_for_reconciliation'
            """,
            (hit["catalogId"], canonical, hit["sha256"]),
        )

    return {
        "catalogId": hit["catalogId"],
        "avatarId": aid,
        "tokenId": str(hit.get("tokenId")),
        "canonicalUrl": canonical,
        "sha256": hit["sha256"],
        "vrmSpec": hit["vrm_spec"],
        "byteLength": int(hit["byte_length"]),
        "identityMode": identity_mode,
        "collectionUpdated": collection_updated,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    hits = [row for row in (report.get("validatedHits") or []) if isinstance(row, dict)]
    if not hits:
        raise SystemExit("validation report contains no binary-proven hits")

    stamp = utc_now()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    reconciled: list[dict[str, Any]] = []
    try:
        conn.execute("BEGIN IMMEDIATE")
        for hit in hits:
            reconciled.append(reconcile_hit(conn, hit, stamp))
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise RuntimeError(
                f"database integrity failed: integrity={integrity!r}, foreign_keys={len(foreign_keys)}"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    collections = sorted({row["catalogId"] for row in reconciled})
    payload = {
        "schema": "moralis-candidate-reconciliation-v1",
        "generatedAt": stamp,
        "sourceReport": str(args.report.relative_to(ROOT)) if args.report.is_relative_to(ROOT) else str(args.report),
        "policy": "existing exact collection identity only; binary VRM proof required; no fuzzy collection creation",
        "summary": {
            "validatedHitsInput": len(hits),
            "reconciledAvatars": len(reconciled),
            "collectionsReconciled": len(collections),
            "collections": collections,
        },
        "reconciled": reconciled,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    conn.close()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = run(args)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
