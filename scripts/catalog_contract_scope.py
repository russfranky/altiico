#!/usr/bin/env python3
"""Resolve every contract identity that belongs to a catalog collection.

`collections.contract` is the convenience primary address. The `contracts`
table is authoritative for additional/migrated addresses. API discovery code
must use this module instead of silently dropping secondary contracts.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any

EVM_ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def text(value: Any) -> str:
    return str(value or "").strip()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def table_columns(conn: sqlite3.Connection, name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({name})")}


def valid_evm_address(value: Any) -> bool:
    return bool(EVM_ADDRESS_RE.fullmatch(text(value)))


def collection_contract_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return collection rows with a normalized `contracts` scan scope.

    The multi-contract table wins when present, but a valid primary contract is
    always retained as a fallback so older DB snapshots remain scannable.
    """
    collection_columns = table_columns(conn, "collections")
    wanted = [
        key
        for key in (
            "id",
            "name",
            "tier",
            "chain",
            "contract",
            "avatar_count",
            "total_supply",
            "max_supply",
        )
        if key in collection_columns
    ]
    rows = [
        dict(row)
        for row in conn.execute(
            f"SELECT {','.join(wanted)} FROM collections ORDER BY name"
        ).fetchall()
    ]

    contracts_by_collection: dict[str, list[dict[str, Any]]] = {}
    if table_exists(conn, "contracts"):
        contract_columns = table_columns(conn, "contracts")
        if {"collection_id", "address", "chain"}.issubset(contract_columns):
            selected = ["collection_id", "address", "chain"]
            if "is_primary" in contract_columns:
                selected.append("is_primary")
            if "token_standard" in contract_columns:
                selected.append("token_standard")
            for raw in conn.execute(
                f"SELECT {','.join(selected)} FROM contracts ORDER BY collection_id,is_primary DESC,address"
            ).fetchall():
                item = dict(raw)
                address = text(item.get("address"))
                if not valid_evm_address(address):
                    continue
                cid = text(item.get("collection_id"))
                if not cid:
                    continue
                contracts_by_collection.setdefault(cid, []).append(
                    {
                        "address": address.lower(),
                        "chain": text(item.get("chain")).lower(),
                        "is_primary": bool(item.get("is_primary")),
                        "token_standard": item.get("token_standard"),
                    }
                )

    out: list[dict[str, Any]] = []
    for row in rows:
        cid = text(row.get("id"))
        contracts = contracts_by_collection.get(cid, [])[:]
        primary_address = text(row.get("contract"))
        primary_chain = text(row.get("chain")).lower()
        if valid_evm_address(primary_address) and not any(
            text(item.get("address")).lower() == primary_address.lower()
            for item in contracts
        ):
            contracts.insert(
                0,
                {
                    "address": primary_address.lower(),
                    "chain": primary_chain,
                    "is_primary": True,
                    "token_standard": None,
                },
            )
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in contracts:
            key = (text(item.get("chain")).lower(), text(item.get("address")).lower())
            if not all(key) or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        row["contracts"] = deduped
        out.append(row)
    return out
