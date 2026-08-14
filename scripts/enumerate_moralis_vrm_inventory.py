#!/usr/bin/env python3
"""Enumerate token-complete VRM link inventories with Moralis.

The sampled Moralis discovery pass is useful for finding leads but cannot prove
"links to all VRMs". This pass walks Moralis cursor pagination to exhaustion for
every registered EVM contract belonging to each supported catalog collection
and records every token ID plus every explicit `.vrm` URL found in normalized
or raw metadata.

A single-contract collection is marked metadata-complete only when:
- pagination reaches the terminal page (no cursor),
- no artificial page/token budget truncated the scan,
- every enumerated token has at least one explicit `.vrm` URL, and
- the enumerated token count is not below the best known supply count.

For multi-contract collections, every registered contract must independently
satisfy those conditions. This is intentionally conservative: a migrated or
secondary contract may make a collection fail until its role is researched, but
no contract can silently disappear from the "all VRMs" denominator.

This is metadata/link evidence, not binary VRM proof. The separate link probe
must structurally validate every URL before final catalog acceptance.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.catalog_contract_scope import collection_contract_rows, valid_evm_address  # noqa: E402
from scripts.discover_moralis_models import inspect_nft  # noqa: E402
from scripts.moralis_client import CHAIN_MAP, MoralisClient  # noqa: E402

DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research.json"
DEFAULT_OUTPUT = ROOT / "data" / "moralis_full_vrm_inventory.json"
VRM_URL_RE = re.compile(r"\.vrm(?:$|[?#])", re.I)
TERMINAL_STATES = {"not_shipped", "unrecoverable"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def integer(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def load_research(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"collections": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload.get("collections"), dict) else {"collections": {}}


def terminal_research_state(research_row: dict[str, Any]) -> str | None:
    inventory = research_row.get("vrm_inventory")
    if not isinstance(inventory, dict) or not inventory.get("evidence"):
        return None
    state = text(inventory.get("state") or inventory.get("coverage")).lower()
    return state if state in TERMINAL_STATES else None


def explicit_vrm_urls(nft: dict[str, Any]) -> list[str]:
    signals = inspect_nft(nft)
    urls = {
        text(candidate.get("url"))
        for candidate in signals.get("modelCandidates") or []
        if isinstance(candidate, dict)
        and text(candidate.get("url"))
        and VRM_URL_RE.search(text(candidate.get("url")))
    }
    return sorted(urls)


def known_supply(row: dict[str, Any], api_total: int | None = None) -> int | None:
    values: list[int] = []
    for key in ("avatar_count", "total_supply", "max_supply"):
        parsed = integer(row.get(key))
        if parsed and parsed > 0:
            values.append(parsed)
    if api_total and api_total > 0:
        values.append(api_total)
    return max(values) if values else None


def coverage_summary(
    *,
    row: dict[str, Any],
    tokens: list[dict[str, Any]],
    cursor_exhausted: bool,
    truncated: bool,
    api_total: int | None,
) -> dict[str, Any]:
    token_ids = {text(token.get("tokenId")) for token in tokens if text(token.get("tokenId"))}
    tokens_with_vrm = {
        text(token.get("tokenId"))
        for token in tokens
        if text(token.get("tokenId")) and token.get("vrmUrls")
    }
    expected = known_supply(row, api_total)
    supply_covered = expected is None or len(token_ids) >= expected
    complete = bool(
        cursor_exhausted
        and not truncated
        and token_ids
        and token_ids == tokens_with_vrm
        and supply_covered
    )
    return {
        "cursorExhausted": cursor_exhausted,
        "truncated": truncated,
        "tokensEnumerated": len(token_ids),
        "tokensWithVrmLinks": len(tokens_with_vrm),
        "tokensMissingVrmLinks": len(token_ids - tokens_with_vrm),
        "apiTotal": api_total,
        "expectedTokens": expected,
        "supplyCovered": supply_covered,
        "metadataComplete": complete,
    }


def contract_scope(row: dict[str, Any]) -> list[dict[str, Any]]:
    contracts = row.get("contracts")
    if isinstance(contracts, list) and contracts:
        out = [
            {
                "address": text(item.get("address")).lower(),
                "chain": text(item.get("chain") or row.get("chain")).lower(),
                "is_primary": bool(item.get("is_primary")),
                "token_standard": item.get("token_standard"),
            }
            for item in contracts
            if isinstance(item, dict)
            and valid_evm_address(item.get("address"))
            and text(item.get("chain") or row.get("chain")).lower() in CHAIN_MAP
        ]
        if out:
            return out
    address = text(row.get("contract")).lower()
    chain = text(row.get("chain")).lower()
    if valid_evm_address(address) and chain in CHAIN_MAP:
        return [
            {
                "address": address,
                "chain": chain,
                "is_primary": True,
                "token_standard": None,
            }
        ]
    return []


async def scan_contract(
    client: MoralisClient,
    row: dict[str, Any],
    contract_row: dict[str, Any],
    *,
    page_size: int = 100,
    max_pages: int = 0,
    max_tokens: int = 0,
) -> dict[str, Any]:
    chain = text(contract_row.get("chain") or row.get("chain")).lower()
    contract = text(contract_row.get("address") or row.get("contract")).lower()
    cursor: str | None = None
    seen_cursors: set[str] = set()
    token_map: dict[str, dict[str, Any]] = {}
    pages = 0
    api_total: int | None = None
    cursor_exhausted = False
    truncated = False
    errors: list[str] = []

    while True:
        try:
            payload = await client.collection_nfts(
                chain, contract, limit=page_size, cursor=cursor
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")
            break

        pages += 1
        total_value = integer(payload.get("total"))
        if total_value is not None:
            api_total = max(api_total or 0, total_value)

        for nft in payload.get("result") or []:
            if not isinstance(nft, dict):
                continue
            token_id = text(nft.get("token_id"))
            if not token_id:
                continue
            urls = explicit_vrm_urls(nft)
            item = token_map.setdefault(
                token_id,
                {
                    "tokenId": token_id,
                    "tokenUri": nft.get("token_uri"),
                    "vrmUrls": [],
                },
            )
            item["vrmUrls"] = sorted(set(item["vrmUrls"]) | set(urls))
            if not item.get("tokenUri") and nft.get("token_uri"):
                item["tokenUri"] = nft.get("token_uri")

            if max_tokens and len(token_map) >= max_tokens:
                truncated = True
                break
        if truncated:
            break

        next_cursor = text(payload.get("cursor"))
        if not next_cursor:
            cursor_exhausted = True
            break
        if next_cursor in seen_cursors:
            errors.append("Moralis returned a repeated cursor")
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        if max_pages and pages >= max_pages:
            truncated = True
            break

    tokens = sorted(
        token_map.values(),
        key=lambda item: (
            0 if text(item.get("tokenId")).isdigit() else 1,
            int(item["tokenId"])
            if text(item.get("tokenId")).isdigit()
            else text(item.get("tokenId")),
        ),
    )
    coverage = coverage_summary(
        row=row,
        tokens=tokens,
        cursor_exhausted=cursor_exhausted,
        truncated=truncated,
        api_total=api_total,
    )
    all_urls = sorted({url for token in tokens for url in token.get("vrmUrls") or []})
    return {
        "chain": chain,
        "contract": contract,
        "isPrimary": bool(contract_row.get("is_primary")),
        "tokenStandard": contract_row.get("token_standard"),
        "pages": pages,
        "error": "; ".join(errors) if errors else None,
        **coverage,
        "uniqueVrmUrls": len(all_urls),
        "vrmUrls": all_urls,
        "tokens": tokens,
    }


async def scan_collection(
    client: MoralisClient,
    row: dict[str, Any],
    *,
    page_size: int = 100,
    max_pages: int = 0,
    max_tokens: int = 0,
) -> dict[str, Any]:
    scopes = contract_scope(row)
    contract_results: list[dict[str, Any]] = []
    for scope in scopes:
        contract_results.append(
            await scan_contract(
                client,
                row,
                scope,
                page_size=page_size,
                max_pages=max_pages,
                max_tokens=max_tokens,
            )
        )

    primary = next(
        (item for item in contract_results if item.get("isPrimary")),
        contract_results[0] if contract_results else None,
    )
    all_urls = sorted(
        {
            url
            for result in contract_results
            for url in result.get("vrmUrls") or []
        }
    )
    tokens = []
    for result in contract_results:
        for token in result.get("tokens") or []:
            tokens.append(
                {
                    **token,
                    "contract": result.get("contract"),
                    "chain": result.get("chain"),
                }
            )
    errors = [
        f"{result.get('contract')}: {result.get('error')}"
        for result in contract_results
        if result.get("error")
    ]
    metadata_complete = bool(contract_results) and all(
        bool(result.get("metadataComplete")) for result in contract_results
    )
    return {
        "catalogId": row.get("id"),
        "name": row.get("name"),
        "chain": primary.get("chain") if primary else text(row.get("chain")).lower(),
        "contract": primary.get("contract") if primary else text(row.get("contract")).lower(),
        "contracts": [result.get("contract") for result in contract_results],
        "contractsScanned": len(contract_results),
        "contractResults": contract_results,
        "pages": sum(int(result.get("pages") or 0) for result in contract_results),
        "error": "; ".join(errors) if errors else None,
        "cursorExhausted": bool(contract_results)
        and all(bool(result.get("cursorExhausted")) for result in contract_results),
        "truncated": any(bool(result.get("truncated")) for result in contract_results),
        "tokensEnumerated": sum(
            int(result.get("tokensEnumerated") or 0) for result in contract_results
        ),
        "tokensWithVrmLinks": sum(
            int(result.get("tokensWithVrmLinks") or 0) for result in contract_results
        ),
        "tokensMissingVrmLinks": sum(
            int(result.get("tokensMissingVrmLinks") or 0) for result in contract_results
        ),
        "apiTotal": sum(int(result.get("apiTotal") or 0) for result in contract_results)
        or None,
        "expectedTokens": sum(
            int(result.get("expectedTokens") or 0) for result in contract_results
        )
        or None,
        "supplyCovered": bool(contract_results)
        and all(bool(result.get("supplyCovered")) for result in contract_results),
        "metadataComplete": metadata_complete,
        "uniqueVrmUrls": len(all_urls),
        "vrmUrls": all_urls,
        "tokens": tokens,
    }


async def run_async(args: argparse.Namespace) -> dict[str, Any]:
    research = load_research(Path(args.research)).get("collections") or {}
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        rows = collection_contract_rows(conn)
    finally:
        conn.close()

    tiers = {part.strip().upper() for part in args.tiers.split(",") if part.strip()}
    candidates = []
    for row in rows:
        if text(row.get("tier")).upper() not in tiers:
            continue
        supported_contracts = [
            item
            for item in row.get("contracts") or []
            if text(item.get("chain")).lower() in CHAIN_MAP
            and valid_evm_address(item.get("address"))
        ]
        if not supported_contracts:
            continue
        row["contracts"] = supported_contracts
        candidates.append(row)

    terminal: list[dict[str, Any]] = []
    scannable: list[dict[str, Any]] = []
    for row in candidates:
        state = terminal_research_state(research.get(text(row.get("id"))) or {})
        if state:
            scopes = contract_scope(row)
            primary = next(
                (item for item in scopes if item.get("is_primary")),
                scopes[0] if scopes else {},
            )
            terminal.append(
                {
                    "catalogId": row.get("id"),
                    "name": row.get("name"),
                    "chain": primary.get("chain") or row.get("chain"),
                    "contract": primary.get("address") or row.get("contract"),
                    "contracts": [item.get("address") for item in scopes],
                    "contractsScanned": 0,
                    "contractResults": [],
                    "terminalResearchState": state,
                    "metadataComplete": True,
                    "tokensEnumerated": 0,
                    "tokensWithVrmLinks": 0,
                    "tokensMissingVrmLinks": 0,
                    "uniqueVrmUrls": 0,
                    "vrmUrls": [],
                    "tokens": [],
                    "pages": 0,
                    "error": None,
                }
            )
        else:
            scannable.append(row)

    semaphore = asyncio.Semaphore(max(1, args.collection_concurrency))
    async with MoralisClient(max_concurrency=args.concurrency) as client:

        async def one(row: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                result = await scan_collection(
                    client,
                    row,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                    max_tokens=args.max_tokens,
                )
                print(
                    f"{result['catalogId']}: {result['contractsScanned']} contracts, "
                    f"{result['tokensEnumerated']} tokens, {result['uniqueVrmUrls']} VRM URLs, "
                    f"complete={result['metadataComplete']}",
                    file=sys.stderr,
                )
                return result

        scanned = await asyncio.gather(*(one(row) for row in scannable))

    collections = sorted(
        [*terminal, *scanned],
        key=lambda row: (text(row.get("name")).lower(), text(row.get("catalogId"))),
    )
    return {
        "schema": "moralis-full-vrm-inventory-v2",
        "generatedAt": now_iso(),
        "policy": (
            "Cursor pagination must exhaust for every registered collection contract and every "
            "enumerated token on every contract must expose an explicit .vrm URL; this proves "
            "metadata/link coverage only, not VRM binary validity."
        ),
        "summary": {
            "collections": len(collections),
            "scannedCollections": len(scanned),
            "contractsScanned": sum(int(row.get("contractsScanned") or 0) for row in scanned),
            "terminalResearchCollections": len(terminal),
            "collectionsWithErrors": sum(bool(row.get("error")) for row in scanned),
            "metadataCompleteCollections": sum(
                bool(row.get("metadataComplete")) for row in collections
            ),
            "tokensEnumerated": sum(
                int(row.get("tokensEnumerated") or 0) for row in scanned
            ),
            "tokensWithVrmLinks": sum(
                int(row.get("tokensWithVrmLinks") or 0) for row in scanned
            ),
            "uniqueVrmUrls": sum(
                int(row.get("uniqueVrmUrls") or 0) for row in scanned
            ),
        },
        "collections": collections,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--research", default=str(DEFAULT_RESEARCH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--tiers", default="A,B,C")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=0, help="0 = exhaust cursor")
    parser.add_argument("--max-tokens", type=int, default=0, help="0 = no artificial token ceiling")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--collection-concurrency", type=int, default=2)
    args = parser.parse_args()
    payload = asyncio.run(run_async(args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
