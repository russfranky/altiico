#!/usr/bin/env python3
"""objkt / Tezos source: token metadata scan for VRM assets.

objkt exposes Tezos NFT metadata through the public data.objkt.com GraphQL API.
This source searches token names/descriptions for VRM / 3D-avatar language and
optionally validates candidate metadata by running VRM-looking URLs through the
partial-GLB extractor.

Search hits are **leads only**. A Tezos token/collection is safe to import only
after token metadata links to a resolvable VRM binary.

Usage:
    python sources/objkt.py --dry-run
    python sources/objkt.py --search "vrm" --validate --dry-run
    python sources/objkt.py --contract KT1... --token-id 123 --validate
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discover_metadata_fields import scan_metadata, validate_candidates  # noqa: E402

OBJKT_GRAPHQL = "https://data.objkt.com/v3/graphql"
TIMEOUT = 30.0
RATE_LIMIT_SLEEP = 0.5
DEFAULT_SEARCH_TERMS = ["VRM", "3d avatar", "metaverse avatar", "virtual avatar"]
VRM_LEAD_HINTS = ("vrm", "3d avatar", "metaverse avatar", "virtual avatar")

SEARCH_QUERY = """
query SearchTokens($term: String!, $limit: Int!) {
  token(
    where: {
      _or: [
        {name: {_ilike: $term}},
        {description: {_ilike: $term}}
      ]
    },
    limit: $limit,
    order_by: {timestamp: desc}
  ) {
    token_id
    name
    description
    artifact_uri
    display_uri
    thumbnail_uri
    metadata
    fa_contract
  }
}
"""

TOKEN_QUERY = """
query Token($contract: String!, $tokenId: String!) {
  token(
    where: {fa_contract: {_eq: $contract}, token_id: {_eq: $tokenId}},
    limit: 1
  ) {
    token_id
    name
    description
    artifact_uri
    display_uri
    thumbnail_uri
    metadata
    fa_contract
  }
}
"""


def graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        OBJKT_GRAPHQL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "superyeti/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("errors"):
        raise ValueError(f"objkt GraphQL error: {data['errors']}")
    return data.get("data") or {}


def _tokens(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        token = payload.get("token")
        if isinstance(token, list):
            return [x for x in token if isinstance(x, dict)]
        data = payload.get("data")
        if data is not payload:
            return _tokens(data)
    return []


def search_tokens(term: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        return _tokens(graphql(SEARCH_QUERY, {"term": f"%{term}%", "limit": limit}))
    except (urllib.error.URLError, ValueError) as e:
        print(f"  objkt search {term!r} failed: {e}", file=sys.stderr)
        return []


def fetch_token(contract: str, token_id: str) -> dict[str, Any] | None:
    try:
        rows = _tokens(graphql(TOKEN_QUERY, {"contract": contract, "tokenId": str(token_id)}))
    except (urllib.error.URLError, ValueError) as e:
        print(f"  objkt token {contract}/{token_id} failed: {e}", file=sys.stderr)
        return None
    return rows[0] if rows else None


def _contract_from(token: dict[str, Any]) -> str | None:
    value = token.get("fa_contract") or token.get("contract")
    if isinstance(value, dict):
        value = value.get("address") or value.get("contract")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _token_id_from(token: dict[str, Any]) -> str | None:
    value = token.get("token_id") or token.get("tokenId") or token.get("id")
    if value is None:
        return None
    return str(value)


def _lead_text(token: dict[str, Any]) -> str:
    fields = []
    for key in ("name", "description", "symbol"):
        val = token.get(key)
        if isinstance(val, str):
            fields.append(val)
    metadata = token.get("metadata")
    if isinstance(metadata, dict):
        for key in ("name", "description"):
            val = metadata.get(key)
            if isinstance(val, str):
                fields.append(val)
    return " ".join(fields).lower()


def is_lead(token: dict[str, Any]) -> bool:
    """Return True for text hits. This is not VRM proof."""
    text = _lead_text(token)
    return any(hint in text for hint in VRM_LEAD_HINTS)


def _metadata_objects(token: dict[str, Any]) -> list[dict[str, Any]]:
    obj: dict[str, Any] = {
        "name": token.get("name"),
        "description": token.get("description"),
        "artifact_uri": token.get("artifact_uri"),
        "display_uri": token.get("display_uri"),
        "thumbnail_uri": token.get("thumbnail_uri"),
    }
    metadata = token.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {"metadata": metadata}
    if isinstance(metadata, dict):
        obj["metadata"] = metadata
    return [obj]


def _candidate_from_token(token: dict[str, Any]) -> dict[str, Any]:
    contract = _contract_from(token)
    token_id = _token_id_from(token)
    return {
        "name": token.get("name"),
        "contract": contract,
        "token_id": token_id,
        "chain": "tezos",
        "lead": is_lead(token),
        "validated": None,
        "vrm_url": None,
        "vrm_spec": None,
        "vrm_field": None,
        "reason": "name/description match" if is_lead(token) else "search hit, no VRM hint",
        "raw": token,
    }


def rewrite_storage_url(url: str) -> str:
    """Rewrite decentralized storage URIs to HTTPS for binary validation.

    IPFS CIDs are case-sensitive, so the CID/path segment is preserved exactly.
    """
    if not isinstance(url, str):
        return url
    lower = url.lower()
    if lower.startswith("ipfs://"):
        cid = url[len("ipfs://"):].lstrip("/")
        if cid.lower().startswith("ipfs/"):
            cid = cid[5:]
        return "https://ipfs.io/ipfs/" + cid
    if lower.startswith("ar://"):
        return "https://arweave.net/" + url[len("ar://"):].lstrip("/")
    if lower.startswith("arweave://"):
        return "https://arweave.net/" + url[len("arweave://"):].lstrip("/")
    return url


def validate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    metadata_objects = _metadata_objects(candidate["raw"])
    pointer_candidates: list[dict[str, Any]] = []
    for obj in metadata_objects:
        pointer_candidates.extend(scan_metadata(obj))
    if not pointer_candidates:
        candidate["validated"] = False
        candidate["reason"] = "no VRM pointer in Tezos token metadata"
        return candidate
    normalized = [
        {**c, "original_url": c["url"], "url": rewrite_storage_url(c["url"])}
        for c in pointer_candidates
    ]
    hits = [hit for hit in validate_candidates(normalized) if hit.get("valid")]
    if hits:
        candidate["validated"] = True
        candidate["vrm_url"] = hits[0]["url"]
        candidate["vrm_spec"] = hits[0].get("vrm_spec")
        candidate["vrm_field"] = hits[0].get("field")
        candidate["reason"] = f"validated VRM pointer ({hits[0].get('path')})"
    else:
        candidate["validated"] = False
        candidate["reason"] = f"{len(pointer_candidates)} pointer(s) found, none validated as GLB/VRM"
    return candidate


def discover_candidates(terms: list[str], validate: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for term in terms:
        for token in search_tokens(term, limit):
            contract = _contract_from(token)
            token_id = _token_id_from(token)
            if not contract or token_id is None:
                continue
            key = (contract, token_id)
            if key in seen:
                continue
            seen.add(key)
            cand = _candidate_from_token(token)
            if validate:
                cand = validate_candidate(cand)
            out.append(cand)
            time.sleep(RATE_LIMIT_SLEEP)
    return out


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def import_validated(candidates: list[dict[str, Any]], db_path: str, dry_run: bool = True) -> dict[str, int]:
    """Insert only validated Tezos VRM collections. Lead-only rows are skipped."""
    valid = [c for c in candidates if c.get("validated") and c.get("contract")]
    if dry_run or not valid:
        return {"checked": len(candidates), "imported": 0, "skipped": len(candidates) - len(valid)}

    conn = sqlite3.connect(db_path)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    imported = 0
    try:
        for c in valid:
            contract = c["contract"]
            collection_id = _slugify(f"tezos-{c.get('name') or contract}")
            conn.execute(
                """
                INSERT OR REPLACE INTO collections
                    (id, name, tier, chain, contract, vrm_param, vrm_url_pattern,
                     source, notes, chain_namespace, chain_reference)
                VALUES (?, ?, 'A', 'tezos', ?, ?, ?, 'objkt', ?, 'tezos', NULL)
                """,
                (
                    collection_id,
                    c.get("name") or contract,
                    contract,
                    c.get("vrm_field"),
                    c.get("vrm_url"),
                    f"Validated via objkt Tezos token metadata at {now}",
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO collection_identifiers
                    (collection_id, namespace, value, chain, contract, token_id,
                     verified_at, resolution_source, chain_namespace,
                     chain_reference, asset_namespace)
                VALUES (?, 'objkt_token', ?, 'tezos', ?, ?, ?, 'objkt',
                        'tezos', NULL, 'fa2')
                """,
                (collection_id, f"{contract}:{c.get('token_id')}", contract, c.get("token_id"), now),
            )
            imported += 1
        conn.commit()
    finally:
        conn.close()
    return {"checked": len(candidates), "imported": imported, "skipped": len(candidates) - imported}


def _print_candidate(c: dict[str, Any]) -> None:
    flag = "VRM" if c.get("validated") else ("LEAD" if c.get("lead") else "   ")
    print(
        f"  [{flag}] tezos {(c.get('name') or '?')[:32]:32s} "
        f"{(c.get('contract') or '?')[:12]}:{c.get('token_id') or '?'} {c.get('reason') or ''}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="objkt Tezos VRM metadata sweep.")
    parser.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    parser.add_argument("--search", action="append",
                        help="search term; repeatable (default: built-in VRM terms)")
    parser.add_argument("--contract", help="Tezos FA2 contract address")
    parser.add_argument("--token-id", help="token id for --contract")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--validate", action="store_true",
                        help="validate candidate token metadata via partial-GLB VRM extraction")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="import validated candidates into collections (never imports leads)")
    parser.add_argument("--dry-run", action="store_true", help="print results; do not write")
    args = parser.parse_args(argv)

    if args.contract or args.token_id:
        if not args.contract or not args.token_id:
            print("ERROR: --contract and --token-id must be provided together", file=sys.stderr)
            return 2
        token = fetch_token(args.contract, args.token_id)
        if not token:
            print("objkt token not found")
            return 1
        candidates = [_candidate_from_token(token)]
        if args.validate:
            candidates[0] = validate_candidate(candidates[0])
    else:
        candidates = discover_candidates(args.search or DEFAULT_SEARCH_TERMS, validate=args.validate, limit=args.limit)

    leads = [c for c in candidates if c.get("lead")]
    valid = [c for c in candidates if c.get("validated")]
    print(f"objkt sweep: {len(candidates)} candidate(s), {len(leads)} lead(s), {len(valid)} validated VRM")
    for c in candidates:
        _print_candidate(c)

    if args.do_import:
        summary = import_validated(candidates, args.db, dry_run=args.dry_run)
        print(f"import: checked={summary['checked']} imported={summary['imported']} skipped={summary['skipped']}")
        if args.dry_run:
            print("(dry run — no DB writes)")
    elif args.dry_run:
        print("(dry run — no DB writes)")
    return 0 if (not args.contract or not args.validate or valid) else 1


if __name__ == "__main__":
    raise SystemExit(main())
