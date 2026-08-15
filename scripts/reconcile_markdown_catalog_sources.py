#!/usr/bin/env python3
"""Non-destructively reconcile curated markdown collection tables into SQLite.

The historical build_index parser starts several tables one line too late. That
can silently omit whole Tier C / Arweave / infrastructure source tables. This
reconciler treats the markdown as an identity lead source without rebuilding or
wiping the mature database:

- parse every collection-bearing markdown table from its real header row;
- match existing rows by id, contract, OpenSea slug, then normalized name;
- fill only blank identity/source fields on matched rows;
- insert missing researched collection identities so completeness auditing can
  expose their remaining gaps instead of dropping them from the denominator;
- never manufacture VRM URLs, license conclusions, social links or lifecycle
  status.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_SOURCE = ROOT / "data" / "vrm_collections.md"
DEFAULT_OUTPUT = ROOT / "data" / "markdown_source_reconciliation.json"

TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")
CONTRACT_RE = re.compile(r"0x[a-fA-F0-9]{40}")
OPENSEA_RE = re.compile(r"(?:https?://)?(?:www\.)?opensea\.io/collection/([^/?#)\s]+)", re.I)
MD_LINK_RE = re.compile(r"\[([^]]+)\]\(([^)]+)\)")

CHAIN_BY_HEADING = {
    "ethereum mainnet": "ethereum",
    "ethereum / base (multi-chain)": "multi",
    "base": "base",
    "optimism": "optimism",
    "polygon": "polygon",
    "shape / other l2s": "shape",
}


@dataclass(frozen=True)
class MarkdownTable:
    h2: str
    h3: str
    header: list[str]
    rows: list[dict[str, str]]
    line: int


def clean_inline(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("†", "").strip()
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def slugify(value: Any) -> str:
    text = clean_inline(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def normalize_name(value: Any) -> str:
    text = clean_inline(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def split_table_line(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def parse_tables(text: str) -> list[MarkdownTable]:
    lines = text.splitlines()
    h2 = ""
    h3 = ""
    tables: list[MarkdownTable] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## ") and not line.startswith("### "):
            h2 = clean_inline(line[3:])
            h3 = ""
            i += 1
            continue
        if line.startswith("### "):
            h3 = clean_inline(line[4:])
            i += 1
            continue
        if (
            line.startswith("|")
            and i + 1 < len(lines)
            and TABLE_SEPARATOR_RE.match(lines[i + 1].strip())
        ):
            header = split_table_line(lines[i])
            rows: list[dict[str, str]] = []
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = split_table_line(lines[j])
                if len(cells) == len(header):
                    rows.append(dict(zip(header, cells)))
                j += 1
            tables.append(MarkdownTable(h2=h2, h3=h3, header=header, rows=rows, line=i + 1))
            i = j
            continue
        i += 1
    return tables


def contract_from(value: Any) -> str | None:
    match = CONTRACT_RE.search(str(value or ""))
    return match.group(0).lower() if match else None


def opensea_slug_from(value: Any) -> str | None:
    raw = str(value or "").strip()
    match = OPENSEA_RE.search(raw)
    if match:
        return match.group(1).strip()
    link = MD_LINK_RE.search(raw)
    if link:
        match = OPENSEA_RE.search(link.group(2))
        if match:
            return match.group(1).strip()
    plain = clean_inline(raw)
    if plain and plain != "—" and " " not in plain and "/" not in plain:
        return plain
    return None


def section_tier(h2: str) -> str | None:
    lowered = h2.lower()
    if lowered.startswith("tier a"):
        return "A"
    if lowered.startswith("tier b"):
        return "B"
    if lowered.startswith("tier c"):
        return "C"
    if lowered.startswith("arweave-native"):
        return "arweave"
    if lowered.startswith("non-ethereum vrm infrastructure"):
        return "infra"
    return None


def row_to_lead(table: MarkdownTable, row: dict[str, str]) -> dict[str, Any] | None:
    tier = section_tier(table.h2)
    if not tier:
        return None

    if tier == "infra":
        name = clean_inline(row.get("Platform"))
        if not name:
            return None
        chain_text = clean_inline(row.get("Chain"))
        chain = chain_text.split(" ", 1)[0].lower().strip("()") if chain_text else "unknown"
        return {
            "id": slugify(name),
            "name": name,
            "tier": "infra",
            "chain": chain,
            "contract": None,
            "opensea_slug": None,
            "notes": clean_inline(row.get("Notes")),
            "source": "curated-markdown",
        }

    name = clean_inline(row.get("Collection"))
    if not name:
        return None

    contract = contract_from(row.get("Contract"))
    raw_slug = row.get("OpenSea slug") or row.get("OpenSea")
    opensea_slug = opensea_slug_from(raw_slug)
    chain = CHAIN_BY_HEADING.get(table.h3.lower(), "unknown")
    if tier == "arweave":
        chain = "arweave"
    if tier == "C" and chain == "unknown" and contract:
        chain = "ethereum"

    lead: dict[str, Any] = {
        "id": opensea_slug or slugify(name),
        "name": name,
        "tier": tier,
        "chain": chain,
        "contract": contract,
        "opensea_slug": opensea_slug,
        "notes": clean_inline(row.get("Notes")),
        "source": "curated-markdown",
    }
    if tier == "A":
        lead["vrm_param"] = clean_inline(row.get("Metadata param")) or None
        sample = clean_inline(row.get("Sample VRM URL"))
        # Keep only as historical source text. A descriptive value is not promoted
        # to a concrete public VRM URL by this identity reconciler.
        lead["source_vrm_reference"] = sample or None
    if tier == "arweave":
        count = clean_inline(row.get("Count"))
        lead["avatar_count"] = int(count) if count.isdigit() else None
        license_text = clean_inline(row.get("License"))
        lead["vrm_license"] = license_text or None
        storage = clean_inline(row.get("Storage"))
        if storage:
            lead["notes"] = " | ".join(part for part in [lead.get("notes"), f"Storage: {storage}"] if part)
    return lead


def collection_leads(text: str) -> list[dict[str, Any]]:
    leads: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for table in parse_tables(text):
        for row in table.rows:
            lead = row_to_lead(table, row)
            if not lead:
                continue
            identity = (
                normalize_name(lead.get("name")),
                str(lead.get("contract") or "").lower() or None,
                str(lead.get("opensea_slug") or "").lower() or None,
            )
            if identity in seen:
                continue
            seen.add(identity)
            lead["source_section"] = table.h2
            lead["source_subsection"] = table.h3 or None
            lead["source_line"] = table.line
            leads.append(lead)
    return leads


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def existing_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute("SELECT * FROM collections")]


def build_indexes(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_contract: dict[str, dict[str, Any]] = {}
    by_slug: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("id"):
            by_id[str(row["id"]).lower()] = row
        contract = str(row.get("contract") or "").lower().strip()
        if contract:
            by_contract[contract] = row
        slug = str(row.get("opensea_slug") or "").lower().strip()
        if slug:
            by_slug[slug] = row
        name = normalize_name(row.get("name"))
        if name:
            by_name[name] = row
    return {"id": by_id, "contract": by_contract, "slug": by_slug, "name": by_name}


def find_match(lead: dict[str, Any], indexes: dict[str, dict[str, dict[str, Any]]]) -> tuple[dict[str, Any] | None, str | None]:
    cid = str(lead.get("id") or "").lower()
    if cid and cid in indexes["id"]:
        return indexes["id"][cid], "id"
    contract = str(lead.get("contract") or "").lower()
    if contract and contract in indexes["contract"]:
        return indexes["contract"][contract], "contract"
    slug = str(lead.get("opensea_slug") or "").lower()
    if slug and slug in indexes["slug"]:
        return indexes["slug"][slug], "opensea_slug"
    name = normalize_name(lead.get("name"))
    if name and name in indexes["name"]:
        return indexes["name"][name], "name"
    return None, None


def non_destructive_updates(
    row: dict[str, Any], lead: dict[str, Any], available: set[str]
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key in (
        "contract",
        "opensea_slug",
        "chain",
        "tier",
        "notes",
        "source",
        "vrm_param",
        "avatar_count",
        "vrm_license",
    ):
        if key not in available:
            continue
        incoming = lead.get(key)
        current = row.get(key)
        if not incoming:
            continue
        if key in {"chain", "tier"} and str(current or "").strip().lower() not in {"", "unknown"}:
            continue
        if key == "notes" and current:
            if str(incoming) not in str(current):
                updates[key] = f"{current} | {incoming}"
            continue
        if key == "source" and current:
            if "curated" not in str(current).lower():
                updates[key] = f"{current}+curated-markdown"
            continue
        if not current or str(current).strip().lower() in {"unknown", "—"}:
            updates[key] = incoming
    return updates


def insert_lead(conn: sqlite3.Connection, lead: dict[str, Any], available: set[str]) -> str:
    payload: dict[str, Any] = {
        "id": lead["id"],
        "name": lead["name"],
        "tier": lead.get("tier"),
        "chain": lead.get("chain"),
        "contract": lead.get("contract"),
        "opensea_slug": lead.get("opensea_slug"),
        "vrm_param": lead.get("vrm_param"),
        "avatar_count": lead.get("avatar_count"),
        "vrm_license": lead.get("vrm_license"),
        "notes": lead.get("notes"),
        "source": lead.get("source"),
    }
    payload = {k: v for k, v in payload.items() if k in available and v is not None}
    columns = list(payload)
    conn.execute(
        f"INSERT INTO collections ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
        [payload[c] for c in columns],
    )
    return str(payload["id"])


def ensure_contract(conn: sqlite3.Connection, collection_id: str, lead: dict[str, Any]) -> None:
    contract = str(lead.get("contract") or "").strip()
    if not contract:
        return
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='contracts'"
    ).fetchone() is None:
        return
    cols = table_columns(conn, "contracts")
    payload = {
        "collection_id": collection_id,
        "address": contract,
        "chain": lead.get("chain") or "ethereum",
        "is_primary": 1,
    }
    payload = {k: v for k, v in payload.items() if k in cols}
    keys = list(payload)
    conn.execute(
        f"INSERT OR IGNORE INTO contracts ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
        [payload[k] for k in keys],
    )


def run(db_path: Path, source_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    leads = collection_leads(source_path.read_text(encoding="utf-8"))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        available = table_columns(conn, "collections")
        rows = existing_rows(conn)
        indexes = build_indexes(rows)
        results: list[dict[str, Any]] = []
        inserted = 0
        updated = 0
        matched = 0
        for lead in leads:
            row, matched_by = find_match(lead, indexes)
            if row:
                matched += 1
                changes = non_destructive_updates(row, lead, available)
                if changes:
                    keys = list(changes)
                    conn.execute(
                        f"UPDATE collections SET {','.join(f'{key}=?' for key in keys)} WHERE id=?",
                        [changes[key] for key in keys] + [row["id"]],
                    )
                    updated += 1
                ensure_contract(conn, str(row["id"]), lead)
                results.append(
                    {
                        "sourceName": lead["name"],
                        "catalogId": row["id"],
                        "action": "updated" if changes else "matched",
                        "matchedBy": matched_by,
                        "updatedFields": sorted(changes),
                    }
                )
                continue

            collection_id = insert_lead(conn, lead, available)
            ensure_contract(conn, collection_id, lead)
            inserted += 1
            results.append(
                {
                    "sourceName": lead["name"],
                    "catalogId": collection_id,
                    "action": "inserted",
                    "matchedBy": None,
                    "updatedFields": [],
                }
            )
            # Add the new row to indexes so later duplicate source rows reconcile.
            new_row = dict(conn.execute("SELECT * FROM collections WHERE id=?", (collection_id,)).fetchone())
            indexes = build_indexes([*indexes["id"].values(), new_row])
        conn.commit()
    finally:
        conn.close()

    payload = {
        "schema": "markdown-catalog-source-reconciliation-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": str(source_path),
        "summary": {
            "sourceLeads": len(leads),
            "matched": matched,
            "updated": updated,
            "inserted": inserted,
        },
        "results": results,
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run(args.db, args.source, args.output)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
