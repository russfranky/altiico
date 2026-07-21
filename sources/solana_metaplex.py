#!/usr/bin/env python3
"""Solana Metaplex collection and file scanning for VRM assets.

Starting with 3D Anvil. Uses public Solana RPC — no API key required.
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parent

# Public Solana mainnet RPC — no API key needed.
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
# Metaplex Token Metadata program (PDA authority for all NFT metadata accounts).
METAPLEX_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQf3nBkRAGxsiZbRrf"
# 3D Anvil (https://3danvil.com) mints .vrm assets on Solana via Metaplex.
# TODO: extract from live catalog once the collection mint address is confirmed.
THREE_D_ANVIL_COLLECTION_MINT: str | None = None

# Gateways for rewriting decentralized storage URIs to HTTPS.
IPFS_GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
    "https://dweb.link/ipfs/",
]
ARWEAVE_GATEWAY = "https://arweave.net/"

# Solana public RPC is rate-limited; be polite.
RPC_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# RPC helpers
# ---------------------------------------------------------------------------


def _rpc_call(method: str, params: list[Any], rpc_url: str = SOLANA_RPC) -> dict:
    """Make a single Solana JSON-RPC call and return the result object.

    Raises urllib.error.URLError or ValueError on failure.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        rpc_url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "superyeti/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=RPC_TIMEOUT) as resp:
        body = resp.read()
    result = json.loads(body)
    if result.get("error"):
        raise ValueError(f"RPC error: {result['error']}")
    return result.get("result", {})


def _decode_length_prefixed(data: bytes, offset: int) -> tuple[str, int]:
    """Decode a 4-byte little-endian length-prefixed UTF-8 string.

    Metaplex metadata accounts store name/symbol/uri as:
        u32 length (LE) | utf8 bytes
    Returns (decoded_string, new_offset).
    """
    if offset + 4 > len(data):
        return "", offset
    (length,) = struct.unpack_from("<I", data, offset)
    start = offset + 4
    end = start + length
    if end > len(data):
        end = len(data)
    raw = data[start:end]
    # Metaplex pads each string field to a 4-byte boundary with null bytes.
    padded_len = ((length + 3) // 4) * 4
    next_offset = start + padded_len
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace").rstrip("\x00"), next_offset


def fetch_metaplex_metadata(mint_address: str, rpc_url: str = SOLANA_RPC) -> dict | None:
    """Fetch on-chain Metaplex metadata for a given NFT mint address.

    Uses getProgramAccounts with a memcmp filter on the mint field (offset 33
    in the metadata account, after the 8-byte discriminator + 32-byte update
    authority + 1-byte mint-account flag). Decodes name, symbol, and the
    off-chain URI from the returned account data.

    Returns {mint, name, symbol, uri} or None on failure.
    """
    try:
        # memcmp filter: offset 33 holds the 32-byte mint address.
        result = _rpc_call(
            "getProgramAccounts",
            [
                METAPLEX_PROGRAM_ID,
                {
                    "encoding": "base64",
                    "filters": [
                        {"memcmp": {"offset": 33, "bytes": mint_address}},
                        {"dataSize": 679},  # typical metadata account size
                    ],
                },
            ],
            rpc_url,
        )
        accounts = result.get("value", []) if isinstance(result, dict) else result
        if not accounts:
            # Retry without dataSize filter — account sizes vary.
            result = _rpc_call(
                "getProgramAccounts",
                [
                    METAPLEX_PROGRAM_ID,
                    {
                        "encoding": "base64",
                        "filters": [
                            {"memcmp": {"offset": 33, "bytes": mint_address}},
                        ],
                    },
                ],
                rpc_url,
            )
            accounts = result.get("value", []) if isinstance(result, dict) else result
        if not accounts:
            return None

        # Take the first matching account.
        acct = accounts[0]
        encoded = acct.get("account", {}).get("data", ["", "base64"])
        if isinstance(encoded, list) and len(encoded) >= 1:
            b64 = encoded[0]
        else:
            return None
        raw = base64.b64decode(b64)

        # Layout: 8-byte discriminator | 32 update authority | 32 mint |
        #         name (len-prefixed) | symbol (len-prefixed) | uri (len-prefixed) | ...
        offset = 8 + 32 + 32  # 72
        name, offset = _decode_length_prefixed(raw, offset)
        symbol, offset = _decode_length_prefixed(raw, offset)
        uri, offset = _decode_length_prefixed(raw, offset)
        return {"mint": mint_address, "name": name, "symbol": symbol, "uri": uri}
    except (urllib.error.URLError, ValueError, KeyError, Exception) as e:  # noqa: BLE001
        print(f"  WARN: fetch_metaplex_metadata failed for {mint_address}: {e}")
        return None


# ---------------------------------------------------------------------------
# Off-chain metadata
# ---------------------------------------------------------------------------


def _rewrite_uri(uri: str) -> str:
    """Rewrite ipfs:// and ar:// URIs to HTTPS gateway URLs."""
    if not uri:
        return uri
    lower = uri.lower()
    if lower.startswith("ipfs://"):
        cid = uri[len("ipfs://"):]
        # Some URIs include a path after the CID.
        return IPFS_GATEWAYS[0] + cid.lstrip("/")
    if lower.startswith("ar://"):
        tx = uri[len("ar://"):]
        return ARWEAVE_GATEWAY + tx.lstrip("/")
    return uri


def fetch_offchain_metadata(uri: str, timeout: float = 15.0) -> dict | None:
    """Fetch and parse the off-chain metadata JSON from a Metaplex URI.

    Handles ipfs:// and ar:// rewriting to HTTPS gateways. Returns the parsed
    JSON dict, or None on failure.
    """
    url = _rewrite_uri(uri)
    if not url:
        return None
    # Try the primary gateway, then fall back to alternates for IPFS.
    candidates = [url]
    if uri.lower().startswith("ipfs://"):
        cid = uri[len("ipfs://"):].lstrip("/")
        for gw in IPFS_GATEWAYS[1:]:
            candidates.append(gw + cid)
    last_err: Exception | None = None
    for cand in candidates:
        try:
            req = urllib.request.Request(
                cand, headers={"User-Agent": "superyeti/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            return None
        except (urllib.error.URLError, ValueError, TimeoutError) as e:  # noqa: BLE001
            last_err = e
            continue
    print(f"  WARN: fetch_offchain_metadata failed for {uri}: {last_err}")
    return None


# ---------------------------------------------------------------------------
# VRM detection
# ---------------------------------------------------------------------------


def _ends_with_vrm(value: str) -> bool:
    """True if a string ends with .vrm (case-insensitive), ignoring query/hash."""
    if not isinstance(value, str):
        return False
    # Strip URL query/fragment before checking extension.
    clean = value.split("?")[0].split("#")[0]
    return clean.lower().endswith(".vrm")


def scan_for_vrm(metadata: dict) -> dict:
    """Recursively search a metadata JSON dict for VRM indicators.

    Detects:
      - Any string value ending in .vrm
      - animation_url ending in .vrm
      - properties.files[].uri where type contains 'vrm' or uri ends in .vrm
      - a vrm_url field

    Returns {has_vrm: bool, vrm_url: str|None, vrm_field: str|None}.
    """
    found_url: str | None = None
    found_field: str | None = None

    def _record(url: str, field: str) -> None:
        nonlocal found_url, found_field
        if found_url is None:
            found_url = url
            found_field = field

    def _walk(obj: Any, path: str = "") -> None:
        nonlocal found_url, found_field
        if found_url is not None:
            return
        if isinstance(obj, dict):
            # Explicit vrm_url field.
            if "vrm_url" in obj:
                v = obj["vrm_url"]
                if isinstance(v, str) and v:
                    _record(v, "vrm_url")
                    return
            # animation_url ending in .vrm.
            if "animation_url" in obj:
                v = obj["animation_url"]
                if _ends_with_vrm(v):
                    _record(v, "animation_url")
                    return
            # properties.files[].uri
            if path == "" and "properties" in obj and isinstance(obj["properties"], dict):
                files = obj["properties"].get("files")
                if isinstance(files, list):
                    for f in files:
                        if found_url is not None:
                            break
                        if isinstance(f, dict):
                            ftype = str(f.get("type", "")).lower()
                            furi = f.get("uri", "")
                            if "vrm" in ftype or _ends_with_vrm(furi):
                                _record(furi, "properties.files[].uri")
                                return
            for k, v in obj.items():
                if found_url is not None:
                    return
                _walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if found_url is not None:
                    return
                _walk(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            if _ends_with_vrm(obj):
                _record(obj, path or "string")

    _walk(metadata)
    return {
        "has_vrm": found_url is not None,
        "vrm_url": found_url,
        "vrm_field": found_field,
    }


# ---------------------------------------------------------------------------
# Collection discovery
# ---------------------------------------------------------------------------


def discover_collections(known_collection_mints: list[str] | None = None) -> list[dict]:
    """Discover VRM-bearing Metaplex collections from known mint addresses.

    For each known collection mint, fetches the on-chain metadata, then fetches
    the off-chain JSON and scans it for VRM indicators.

    Returns a list of dicts:
        {mint, name, symbol, uri, has_vrm, vrm_url, vrm_field}

    If no known mints are provided, returns an empty list — discovery on
    Solana requires manual leads (no chain-wide VRM registry exists).
    """
    if not known_collection_mints:
        print(
            "No known collection mints provided. Solana discovery requires "
            "manual leads — no chain-wide VRM registry exists."
        )
        return []

    entries: list[dict] = []
    for mint in known_collection_mints:
        meta = fetch_metaplex_metadata(mint)
        if not meta:
            entries.append(
                {
                    "mint": mint,
                    "name": None,
                    "symbol": None,
                    "uri": None,
                    "has_vrm": False,
                    "vrm_url": None,
                    "vrm_field": None,
                }
            )
            continue
        offchain = None
        if meta.get("uri"):
            offchain = fetch_offchain_metadata(meta["uri"])
        vrm = {"has_vrm": False, "vrm_url": None, "vrm_field": None}
        if offchain:
            vrm = scan_for_vrm(offchain)
        entries.append(
            {
                "mint": mint,
                "name": meta.get("name"),
                "symbol": meta.get("symbol"),
                "uri": meta.get("uri"),
                "has_vrm": vrm["has_vrm"],
                "vrm_url": vrm["vrm_url"],
                "vrm_field": vrm["vrm_field"],
            }
        )
    return entries


# ---------------------------------------------------------------------------
# DB import
# ---------------------------------------------------------------------------


def import_to_db(entries: list[dict], db_path: str) -> dict:
    """Upsert VRM-bearing Metaplex collections into the SQLite DB.

    For each entry with has_vrm=True:
      - collections row: id=solana_{mint[:12]}, chain='solana',
        chain_namespace='solana', chain_reference='mainnet-beta',
        contract=mint, vrm_param=vrm_field, source='solana_metaplex'.
      - collection_identifiers row: namespace='metaplex_mint', value=mint,
        chain_namespace='solana', chain_reference='mainnet-beta'.

    Returns {imported: N, errors: [...]}.
    """
    summary: dict[str, Any] = {"imported": 0, "errors": []}
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    for e in entries:
        if not e.get("has_vrm"):
            continue
        mint = e.get("mint", "")
        if not mint:
            summary["errors"].append("entry missing mint")
            continue
        try:
            collection_id = f"solana_{mint[:12]}"
            name = e.get("name") or collection_id
            symbol = e.get("symbol") or None
            uri = e.get("uri") or None
            vrm_field = e.get("vrm_field") or None
            vrm_url = e.get("vrm_url") or None

            conn.execute(
                """
                INSERT INTO collections
                    (id, name, chain, chain_namespace, chain_reference, contract,
                     vrm_param, vrm_url_https, source, notes)
                VALUES (?, ?, 'solana', 'solana', 'mainnet-beta', ?, ?, ?, 'solana_metaplex', ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    chain='solana',
                    chain_namespace='solana',
                    chain_reference='mainnet-beta',
                    contract=COALESCE(NULLIF(excluded.contract, ''), collections.contract),
                    vrm_param=COALESCE(NULLIF(excluded.vrm_param, ''), collections.vrm_param),
                    vrm_url_https=COALESCE(NULLIF(excluded.vrm_url_https, ''), collections.vrm_url_https),
                    source='solana_metaplex'
                """,
                (
                    collection_id,
                    name,
                    mint,
                    vrm_field,
                    vrm_url,
                    f"Solana Metaplex collection {symbol or ''} (mint {mint})".strip(),
                ),
            )

            conn.execute(
                """
                INSERT INTO collection_identifiers
                    (collection_id, namespace, value, chain_namespace, chain_reference,
                     resolution_source, verified_at)
                VALUES (?, 'metaplex_mint', ?, 'solana', 'mainnet-beta', 'solana_metaplex', ?)
                ON CONFLICT(collection_id, namespace, value) DO UPDATE SET
                    chain_namespace='solana',
                    chain_reference='mainnet-beta',
                    resolution_source='solana_metaplex',
                    verified_at=excluded.verified_at
                """,
                (collection_id, mint, now_iso),
            )

            summary["imported"] += 1
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"{mint}: {exc}")

    conn.commit()
    conn.close()
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for Solana Metaplex VRM scanning."""
    parser = argparse.ArgumentParser(
        description="Scan Solana Metaplex collections for VRM assets."
    )
    parser.add_argument(
        "--db",
        default=str(REPO_ROOT / "data" / "vrm_index.db"),
        help="Path to the SQLite DB (default: data/vrm_index.db)",
    )
    parser.add_argument(
        "--mint",
        help="Scan a single collection mint address (Metaplex mint).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and print results; do not write to the DB.",
    )
    args = parser.parse_args()

    if args.mint:
        mints = [args.mint]
    elif THREE_D_ANVIL_COLLECTION_MINT:
        mints = [THREE_D_ANVIL_COLLECTION_MINT]
    else:
        mints = []

    print("Solana Metaplex VRM scanner")
    print(f"  RPC: {SOLANA_RPC}")
    if not mints:
        print(
            "  No collection mints configured. Set THREE_D_ANVIL_COLLECTION_MINT "
            "or pass --mint <address>."
        )
        if not args.dry_run:
            return
        # In dry-run with no mints, still show the discovery note.
        discover_collections([])
        return

    print(f"  Scanning {len(mints)} collection mint(s)...")
    entries = discover_collections(mints)

    for e in entries:
        flag = "VRM" if e.get("has_vrm") else "   "
        print(
            f"  [{flag}] {e.get('mint', '?')[:12]}...  "
            f"{e.get('name') or '?':30s}  "
            f"field={e.get('vrm_field') or '-'}  url={e.get('vrm_url') or '-'}"
        )

    vrm_count = sum(1 for e in entries if e.get("has_vrm"))
    print(f"\nScanned: {len(entries)}  VRM: {vrm_count}")

    if args.dry_run:
        print("(dry run — no DB writes)")
        return

    summary = import_to_db(entries, args.db)
    print(f"Imported: {summary['imported']}")
    if summary["errors"]:
        print(f"Errors ({len(summary['errors'])}):")
        for err in summary["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
