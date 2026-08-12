#!/usr/bin/env python3
"""Reconcile binary-proven Moralis hits into already-identified catalog records.

This is intentionally narrow. It never creates collections and never matches by
name. A hit must target an existing catalog ID whose chain+contract identity
matches the validation report. Complete VRM proofs are stored in vrm_metadata,
and an existing avatar is linked only when its model URL already matches the
validated asset. New avatar rows are never invented from a bounded sample.

The JSON reconciliation artifact is cumulative: later zero-hit runs preserve
previously reconciled proof rows instead of erasing historical evidence.
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


def matching_existing_avatar(
    conn: sqlite3.Connection,
    collection_id: str,
    canonical: str,
    transport: str,
) -> sqlite3.Row | None:
    if not table_exists(conn, "avatars"):
        return None
    cols = columns(conn, "avatars")
    if not {"id", "collection_id", "model_file_url"} <= cols:
        return None
    return conn.execute(
        """
        SELECT * FROM avatars
        WHERE collection_id=? AND model_file_url IN (?, ?)
        ORDER BY id LIMIT 1
        """,
        (collection_id, canonical, transport),
    ).fetchone()


def link_existing_avatar(
    conn: sqlite3.Connection,
    avatar: sqlite3.Row | None,
    canonical: str,
    transport: str,
    stamp: str,
) -> str | None:
    if avatar is None:
        return None
    aid = str(avatar["id"])
    avatar_cols = columns(conn, "avatars")
    updates = {
        "model_file_url": transport,
        "reachable": 1,
        "check_status": "ok_vrm",
        "checked_at": stamp,
    }
    clean = {key: value for key, value in updates.items() if key in avatar_cols}
    if clean:
        conn.execute(
            f"UPDATE avatars SET {', '.join(f'{key}=?' for key in clean)} WHERE id=?",
            (*clean.values(), aid),
        )
    if table_exists(conn, "avatar_vrm"):
        upsert_dynamic(
            conn,
            "avatar_vrm",
            {"avatar_id": aid, "vrm_source_url": canonical},
            "avatar_id",
        )
    return aid


def reconcile_hit(
    conn: sqlite3.Connection, hit: dict[str, Any], stamp: str
) -> dict[str, Any]:
    if not complete_proof(hit):
        raise ValueError("hit lacks complete binary VRM proof")
    ok, identity_mode = identity_matches(conn, hit)
    if not ok:
        raise ValueError(f"identity rejected: {identity_mode}")

    canonical = str(hit["canonical_url"])
    transport = str(hit.get("transport_url") or canonical)
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

    existing_avatar = matching_existing_avatar(
        conn, str(hit["catalogId"]), canonical, transport
    )
    linked_avatar_id = link_existing_avatar(
        conn,
        existing_avatar,
        canonical,
        transport,
        str(hit.get("observedAt") or stamp),
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
        "tokenId": str(hit.get("tokenId") or ""),
        "canonicalUrl": canonical,
        "sha256": hit["sha256"],
        "vrmSpec": hit["vrm_spec"],
        "byteLength": int(hit["byte_length"]),
        "identityMode": identity_mode,
        "linkedExistingAvatarId": linked_avatar_id,
        "collectionUpdated": collection_updated,
    }


def proof_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("catalogId") or ""),
        str(row.get("canonicalUrl") or ""),
        str(row.get("sha256") or ""),
    )


def load_previous_reconciled(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if payload.get("schema") != "moralis-candidate-reconciliation-v1":
        return []
    return [row for row in (payload.get("reconciled") or []) if isinstance(row, dict)]


def merge_reconciled(
    previous: list[dict[str, Any]], current: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_key = {proof_key(row): row for row in previous if all(proof_key(row))}
    for row in current:
        if all(proof_key(row)):
            by_key[proof_key(row)] = row
    return sorted(
        by_key.values(),
        key=lambda row: (
            str(row.get("catalogId") or ""),
            str(row.get("tokenId") or ""),
            str(row.get("canonicalUrl") or ""),
        ),
    )


def reconciliation_payload(
    args: argparse.Namespace,
    hits: list[dict[str, Any]],
    current: list[dict[str, Any]],
    cumulative: list[dict[str, Any]],
    stamp: str,
) -> dict[str, Any]:
    current_collections = sorted({row["catalogId"] for row in current})
    cumulative_collections = sorted({row["catalogId"] for row in cumulative})
    linked_this_run = sum(bool(row.get("linkedExistingAvatarId")) for row in current)
    linked_cumulative = sum(bool(row.get("linkedExistingAvatarId")) for row in cumulative)
    return {
        "schema": "moralis-candidate-reconciliation-v1",
        "generatedAt": stamp,
        "sourceReport": str(args.report.relative_to(ROOT)) if args.report.is_relative_to(ROOT) else str(args.report),
        "policy": (
            "existing exact collection identity only; binary VRM proof required; "
            "no fuzzy collection creation and no avatar creation from bounded samples; "
            "reconciled proof rows are retained cumulatively across recurring runs"
        ),
        "summary": {
            "validatedHitsInput": len(hits),
            "binaryProofRowsStoredThisRun": len(current),
            "cumulativeBinaryProofRows": len(cumulative),
            "existingAvatarsLinkedThisRun": linked_this_run,
            "cumulativeExistingAvatarsLinked": linked_cumulative,
            "collectionsReconciledThisRun": len(current_collections),
            "collectionsThisRun": current_collections,
            "cumulativeCollectionsReconciled": len(cumulative_collections),
            "cumulativeCollections": cumulative_collections,
        },
        "reconciled": cumulative,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    hits = [row for row in (report.get("validatedHits") or []) if isinstance(row, dict)]
    stamp = utc_now()
    previous = load_previous_reconciled(args.output)
    current: list[dict[str, Any]] = []

    if hits:
        conn = sqlite3.connect(args.db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            for hit in hits:
                current.append(reconcile_hit(conn, hit, stamp))
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
        finally:
            conn.close()

    cumulative = merge_reconciled(previous, current)
    payload = reconciliation_payload(args, hits, current, cumulative, stamp)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
