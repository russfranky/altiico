#!/usr/bin/env python3
"""Audit whether DickButtVerse CDN asset numbers map to ERC-721 token IDs.

This is a bounded identity audit, not an inventory importer. It reads ownerOf and
tokenURI from the exact DickButtVerse Ethereum contract for representative token
IDs, fetches the returned metadata, and checks whether any concrete VRM/GLB model
reference uses the same numeric ID.

A matching sample strengthens identity evidence only. It never creates avatars,
changes supply, or marks the collection bulk-ready.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.chain_registry import CHAINS  # noqa: E402

COLLECTION_ID = "dickbuttverse"
CONTRACT = "0xd47d8672e45a7204057baaa3622a3fa276d651e3"
OWNER_OF_SELECTOR = "6352211e"
TOKEN_URI_SELECTOR = "c87b56dd"
DEFAULT_RECONCILIATION = ROOT / "data" / "moralis_candidate_reconciliation.json"
DEFAULT_OUTPUT = ROOT / "data" / "dickbuttverse_onchain_identity.json"
MODEL_SUFFIXES = (".vrm", ".glb", ".gltf")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_uint_call(selector: str, value: int) -> str:
    if value < 0:
        raise ValueError("uint256 value must be non-negative")
    return "0x" + selector + format(value, "064x")


def decode_address(result: str | None) -> str | None:
    if not isinstance(result, str) or not result.startswith("0x") or len(result) < 42:
        return None
    raw = result[2:]
    if len(raw) < 64:
        return None
    value = raw[-40:]
    if value == "0" * 40:
        return None
    return "0x" + value.lower()


def decode_abi_string(result: str | None) -> str | None:
    if not isinstance(result, str) or not result.startswith("0x"):
        return None
    try:
        payload = bytes.fromhex(result[2:])
    except ValueError:
        return None
    if len(payload) < 64:
        return None
    offset = int.from_bytes(payload[:32], "big")
    if offset < 0 or offset + 32 > len(payload):
        return None
    length = int.from_bytes(payload[offset : offset + 32], "big")
    start = offset + 32
    end = start + length
    if end > len(payload):
        return None
    try:
        return payload[start:end].decode("utf-8")
    except UnicodeDecodeError:
        return None


def rpc_call(session: requests.Session, rpc: str, data: str, timeout: float) -> dict[str, Any]:
    response = session.post(
        rpc,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [{"to": CONTRACT, "data": data}, "latest"],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("RPC returned a non-object")
    return payload


def resilient_rpc_call(
    session: requests.Session,
    data: str,
    timeout: float,
    attempts: int = 3,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    errors: list[str] = []
    for rpc in CHAINS["ethereum"].rpc_urls:
        for attempt in range(1, attempts + 1):
            try:
                payload = rpc_call(session, rpc, data, timeout)
                return payload, rpc, None
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rpc} attempt {attempt}: {type(exc).__name__}: {exc}"[:500])
                if attempt < attempts:
                    time.sleep(min(3.0, 0.5 * attempt))
    return None, None, "; ".join(errors[-4:])


def proven_token_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    values: set[int] = set()
    for row in payload.get("reconciled") or []:
        if not isinstance(row, dict) or row.get("catalogId") != COLLECTION_ID:
            continue
        try:
            values.add(int(str(row.get("tokenId"))))
        except (TypeError, ValueError):
            continue
    return values


def sample_ids(proven: set[int], extras: Iterable[int], limit: int) -> list[int]:
    anchors = {0, 1, 10, 100, 1000, 1696, 2496, 3225, 4383, 4914, 5349, 5362}
    anchors.update(int(value) for value in extras if int(value) >= 0)
    anchors.update(proven)
    ordered = sorted(anchors)
    if limit <= 0 or len(ordered) <= limit:
        return ordered
    must = sorted({value for value in anchors if value in {0, 1696, 3225, 4914, 5349, 5362}})
    remaining = [value for value in ordered if value not in must]
    keep = max(0, limit - len(must))
    if keep >= len(remaining):
        return sorted(must + remaining)
    if keep == 0:
        return must[:limit]
    selected = [remaining[round(i * (len(remaining) - 1) / max(1, keep - 1))] for i in range(keep)]
    return sorted(set(must + selected))[:limit]


def url_numeric_tail(url: str | None) -> int | None:
    if not url:
        return None
    path = urlsplit(url).path.rstrip("/")
    match = re.search(r"(?:^|/)(\d+)(?:\.[A-Za-z0-9]+)?$", path)
    return int(match.group(1)) if match else None


def model_urls(value: Any, *, max_nodes: int = 5000) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    stack: list[tuple[str, Any]] = [("$", value)]
    seen = 0
    while stack and seen < max_nodes:
        path, current = stack.pop()
        seen += 1
        if isinstance(current, dict):
            for key, child in current.items():
                stack.append((f"{path}.{key}", child))
        elif isinstance(current, list):
            for index, child in enumerate(current):
                stack.append((f"{path}[{index}]", child))
        elif isinstance(current, str):
            text = current.strip()
            low = urlsplit(text).path.lower()
            if text.startswith(("http://", "https://", "ipfs://", "ar://")) and low.endswith(MODEL_SUFFIXES):
                found.append({"path": path, "url": text})
    unique: dict[str, dict[str, str]] = {}
    for item in found:
        unique.setdefault(item["url"], item)
    return list(unique.values())


def fetch_metadata(session: requests.Session, url: str, timeout: float) -> tuple[dict[str, Any] | None, str | None]:
    if not url.startswith(("http://", "https://")):
        return None, "unsupported_metadata_transport"
    try:
        response = session.get(url, timeout=timeout, headers={"Accept": "application/json", "User-Agent": "vrm-catalog/1.0"})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None, "metadata_not_object"
        return data, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"[:500]


def inspect_token(session: requests.Session, token_id: int, timeout: float) -> dict[str, Any]:
    owner_payload, owner_rpc, owner_error = resilient_rpc_call(
        session, encode_uint_call(OWNER_OF_SELECTOR, token_id), timeout
    )
    uri_payload, uri_rpc, uri_error = resilient_rpc_call(
        session, encode_uint_call(TOKEN_URI_SELECTOR, token_id), timeout
    )
    owner = decode_address((owner_payload or {}).get("result"))
    token_uri = decode_abi_string((uri_payload or {}).get("result"))
    owner_revert = (owner_payload or {}).get("error") if owner_payload else None
    uri_revert = (uri_payload or {}).get("error") if uri_payload else None
    metadata, metadata_error = fetch_metadata(session, token_uri, timeout) if token_uri else (None, None)
    models = model_urls(metadata) if metadata else []
    matching_models = [item for item in models if url_numeric_tail(item["url"]) == token_id]
    return {
        "tokenId": token_id,
        "owner": owner,
        "ownerRpc": owner_rpc,
        "ownerError": owner_error,
        "ownerRevert": owner_revert,
        "tokenUri": token_uri,
        "tokenUriRpc": uri_rpc,
        "tokenUriError": uri_error,
        "tokenUriRevert": uri_revert,
        "tokenUriNumericTail": url_numeric_tail(token_uri),
        "metadataError": metadata_error,
        "modelCandidates": models,
        "matchingModelCandidates": matching_models,
        "tokenExists": bool(owner or token_uri),
        "tokenUriIdMatches": bool(token_uri and url_numeric_tail(token_uri) == token_id),
        "modelIdMatches": bool(matching_models),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECONCILIATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--extra-id", action="append", type=int, default=[])
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    proven = proven_token_ids(args.reconciliation)
    ids = sample_ids(proven, args.extra_id, args.limit)
    with requests.Session() as session:
        rows = [inspect_token(session, token_id, args.timeout) for token_id in ids]

    existing = [row for row in rows if row["tokenExists"]]
    uri_matches = [row for row in existing if row["tokenUriIdMatches"]]
    model_matches = [row for row in existing if row["modelIdMatches"]]
    payload = {
        "schema": "dickbuttverse-onchain-identity-audit-v1",
        "generatedAt": now_iso(),
        "collection": {
            "catalogId": COLLECTION_ID,
            "chain": "ethereum",
            "contract": CONTRACT,
        },
        "policy": (
            "bounded identity evidence only; ownerOf/tokenURI and metadata are read-only; "
            "matching samples do not establish complete inventory or justify bulk staging"
        ),
        "summary": {
            "idsInspected": len(rows),
            "knownBinaryProofIdsInInput": len(proven),
            "tokensObservedOnchain": len(existing),
            "tokenUriIdMatches": len(uri_matches),
            "metadataModelIdMatches": len(model_matches),
            "tokensWithoutOnchainEvidence": len(rows) - len(existing),
        },
        "results": rows,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
