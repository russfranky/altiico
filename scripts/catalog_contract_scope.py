#!/usr/bin/env python3
"""Resolve every contract identity that belongs to a catalog collection.

`collections.contract` is the convenience primary address. The `contracts`
table is authoritative for additional/migrated addresses. Curated research may
also declare related contracts before they have been materialized into SQLite.
API discovery code must use this module instead of silently dropping either
source of secondary identities.
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


def research_contracts(
    research: dict[str, Any] | None, collection_id: str, fallback_chain: str
) -> list[dict[str, Any]]:
    if not research:
        return []
    collections = research.get("collections") if isinstance(research, dict) else None
    if not isinstance(collections, dict):
        return []
    row = collections.get(collection_id)
    if not isinstance(row, dict):
        return []
    identity = row.get("identity")
    if not isinstance(identity, dict):
        return []

    items: list[dict[str, Any]] = []
    primary = text(identity.get("contract"))
    chain = text(identity.get("chain") or fallback_chain).lower()
    if valid_evm_address(primary):
        items.append(
            {
                "address": primary.lower(),
                "chain": chain,
                "is_primary": True,
                "token_standard": identity.get("token_standard"),
                "role": "primary",
            }
        )

    raw_contracts = identity.get("contracts")
    if isinstance(raw_contracts, list):
        for raw in raw_contracts:
            if isinstance(raw, str):
                address = text(raw)
                item_chain = chain
                is_primary = address.lower() == primary.lower() if primary else False
                token_standard = None
                role = None
            elif isinstance(raw, dict):
                address = text(raw.get("address") or raw.get("contract"))
                item_chain = text(raw.get("chain") or chain).lower()
                is_primary = bool(raw.get("is_primary")) or (
                    bool(primary) and address.lower() == primary.lower()
                )
                token_standard = raw.get("token_standard")
                role = raw.get("role")
            else:
                continue
            if not valid_evm_address(address):
                continue
            items.append(
                {
                    "address": address.lower(),
                    "chain": item_chain,
                    "is_primary": is_primary,
                    "token_standard": token_standard,
                    "role": role,
                }
            )
    return items


def collection_contract_rows(
    conn: sqlite3.Connection, research: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Return collection rows with a normalized `contracts` scan scope.

    Sources are merged conservatively: SQLite `contracts`, the collection's
    primary convenience address, then any evidence-backed related contracts in
    curated research. Older DB snapshots therefore stay scannable while newly
    discovered migration identities can immediately enter API coverage.
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
            order = "collection_id"
            if "is_primary" in contract_columns:
                order += ",is_primary DESC"
            order += ",address"
            for raw in conn.execute(
                f"SELECT {','.join(selected)} FROM contracts ORDER BY {order}"
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
                        "role": None,
                    }
                )

    out: list[dict[str, Any]] = []
    for row in rows:
        cid = text(row.get("id"))
        contracts = contracts_by_collection.get(cid, [])[:]
        primary_address = text(row.get("contract"))
        primary_chain = text(row.get("chain")).lower()
        if valid_evm_address(primary_address):
            contracts.append(
                {
                    "address": primary_address.lower(),
                    "chain": primary_chain,
                    "is_primary": True,
                    "token_standard": None,
                    "role": "primary",
                }
            )
        contracts.extend(research_contracts(research, cid, primary_chain))

        deduped: list[dict[str, Any]] = []
        index: dict[tuple[str, str], int] = {}
        for item in contracts:
            key = (
                text(item.get("chain")).lower(),
                text(item.get("address")).lower(),
            )
            if not all(key):
                continue
            if key in index:
                existing = deduped[index[key]]
                existing["is_primary"] = bool(
                    existing.get("is_primary") or item.get("is_primary")
                )
                for field in ("token_standard", "role"):
                    if not existing.get(field) and item.get(field):
                        existing[field] = item[field]
                continue
            index[key] = len(deduped)
            deduped.append(item)
        deduped.sort(
            key=lambda item: (
                0 if item.get("is_primary") else 1,
                text(item.get("chain")),
                text(item.get("address")),
            )
        )
        row["contracts"] = deduped
        out.append(row)
    return out
