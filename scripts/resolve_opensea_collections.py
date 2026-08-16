#!/usr/bin/env python3
"""Resolve OpenSea collection identity for (chain, contract, token_id) tuples.

OpenSea's shared storefront contract (0x495f947276749ce646f68ac8c248420045cb7b5e)
is an ERC-1155 contract that hosts assets from MANY different OpenSea collections.
The contract address alone cannot identify a collection, so this module implements
a resolution hierarchy (highest priority first):

  1. Known OpenSea slug (from overrides YAML or collection_identifiers table):
     use GET /collection/{slug}/nfts — authoritative for OpenSea grouping.
  2. Contract + token ID: fetch the individual NFT via
     GET /chain/{chain}/contract/{contract}/nfts/{token_id}, read nft.collection
     from the response — high reliability.
  3. Contract sweep: enumerate all NFTs via
     GET /chain/{chain}/contract/{contract}/nfts, group by nft.collection —
     high reliability but expensive; only when allow_sweep=True.
  4. Creator encoded in token ID (high 160 bits for shared storefront): a
     discovery hint only, never authoritative.
  5. Token-ID range: UNSAFE, do not use.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

# Make sibling module importable whether run as a script or a package.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))

from scripts.opensea_client import OpenSeaClient  # noqa: E402

# --------------------------------------------------------------------------- consts

SHARED_STOREFRONT_CONTRACTS: set[str] = {
    "0x495f947276749ce646f68ac8c248420045cb7b5e",  # Ethereum OpenSea shared storefront
    "0x2953399124f0cbb46d2cbacd8a89cf0599974963",  # Polygon OpenSea shared storefront
}

_REPO_ROOT = _SCRIPT_DIR.parent
_OVERRIDES_PATH = _REPO_ROOT / "data" / "opensea_collection_overrides.yaml"
_DEFAULT_DB = _REPO_ROOT / "data" / "vrm_index.db"


# --------------------------------------------------------------------------- helpers


def load_overrides(path: Optional[str | Path] = None) -> dict[str, Any]:
    """Read data/opensea_collection_overrides.yaml and return the parsed dict.

    Returns an empty dict if the file is missing.
    """
    p = Path(path) if path else _OVERRIDES_PATH
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        return {}
    return data or {}


def _shared_storefront_contracts_from_overrides(
    overrides: dict[str, Any],
) -> set[str]:
    """Merge the hardcoded set with any contracts listed in the overrides YAML."""
    contracts = set(SHARED_STOREFRONT_CONTRACTS)
    for addr in overrides.get("shared_storefront_contracts", []) or []:
        if isinstance(addr, str):
            contracts.add(addr.lower())
    return contracts


def _lookup_slug_in_overrides(
    overrides: dict[str, Any],
    chain: str,
    contract: str,
    token_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Search the overrides YAML for a matching slug.

    Returns (slug, collection_id) or (None, None).

    Disambiguation rules for shared-storefront contracts with multiple records:
    - If token_id is given and a record has a matching representative_token_id,
      return that record.
    - If token_id is given but no record has a matching representative_token_id,
      return None (fall through to API lookup rather than guessing).
    - If no token_id is given, only return a match when exactly one record
      exists for this contract (unambiguous). Multiple records with no
      disambiguator means we cannot know which collection — return None so the
      shared-storefront guard raises.
    """
    contract_lc = contract.lower()
    matches: list[dict[str, Any]] = []
    for rec in overrides.get("collections", []) or []:
        rec_contract = (rec.get("contract") or "").lower()
        if rec_contract == contract_lc and rec.get("chain") == chain:
            matches.append(rec)

    if not matches:
        return None, None

    # If a token_id was provided, prefer an exact representative_token_id match.
    if token_id:
        for rec in matches:
            rep = rec.get("representative_token_id")
            if rep is not None and str(rep) == str(token_id):
                slug = rec.get("opensea_slug")
                if slug:
                    return slug, rec.get("collection_id")
        # No exact match — do NOT guess; fall through to API lookup.
        return None, None

    # No token_id: only return a match if unambiguous (exactly one record).
    if len(matches) == 1:
        slug = matches[0].get("opensea_slug")
        if slug:
            return slug, matches[0].get("collection_id")

    # Multiple records, no disambiguator — cannot resolve safely.
    return None, None


def _lookup_slug_in_db(
    db_path: str | Path,
    chain: str,
    contract: str,
    token_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Look up a known slug in the collection_identifiers table.

    Returns (slug, collection_id) or (None, None).
    """
    p = Path(db_path)
    if not p.exists():
        return None, None
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        # Prefer an exact (chain, contract, token_id) match first.
        if token_id:
            row = conn.execute(
                "SELECT collection_id, value FROM collection_identifiers "
                "WHERE namespace='opensea_slug' AND chain=? AND contract=? "
                "AND token_id=? LIMIT 1",
                (chain, contract.lower(), str(token_id)),
            ).fetchone()
            if row:
                return row["value"], row["collection_id"]
        # Fall back to any slug row for this contract.
        row = conn.execute(
            "SELECT collection_id, value FROM collection_identifiers "
            "WHERE namespace='opensea_slug' AND chain=? AND contract=? LIMIT 1",
            (chain, contract.lower()),
        ).fetchone()
        if row:
            return row["value"], row["collection_id"]
    except sqlite3.OperationalError:
        # Table may not exist yet.
        return None, None
    finally:
        conn.close()
    return None, None


def _extract_collection_slug(nft_resp: dict[str, Any]) -> Optional[str]:
    """Extract the collection slug from an OpenSea GET /nfts/{token_id} response.

    OpenSea v2 returns {"nft": {"collection": "slug", ...}} but the shape has
    varied across releases, so try several known locations.
    """
    nft = nft_resp.get("nft") if isinstance(nft_resp, dict) else None
    if not nft and isinstance(nft_resp, dict):
        # Some responses are the NFT object directly.
        nft = nft_resp
    if not isinstance(nft, dict):
        return None
    # Field has appeared as "collection" (string slug) or nested object.
    col = nft.get("collection")
    if isinstance(col, str) and col:
        return col
    if isinstance(col, dict):
        slug = col.get("slug") or col.get("name")
        if isinstance(slug, str) and slug:
            return slug
    return None


# --------------------------------------------------------------------------- core


async def resolve(
    client: OpenSeaClient,
    chain: str,
    contract: str,
    token_id: Optional[str] = None,
    slug: Optional[str] = None,
    *,
    db_path: Optional[str | Path] = None,
    allow_sweep: bool = False,
) -> dict[str, Any]:
    """Resolve an OpenSea collection for the given identifiers.

    Returns a dict with keys: collection_id, opensea_slug, resolution_source.
    Raises ValueError if a shared-storefront contract is given without a
    token_id or slug.
    """
    contract_lc = contract.lower()
    overrides = load_overrides()
    shared_contracts = _shared_storefront_contracts_from_overrides(overrides)

    # --- 1. Explicit slug argument -------------------------------------------
    if slug:
        cid = None
        # Try to enrich with a collection_id from overrides/DB.
        for rec in overrides.get("collections", []) or []:
            if rec.get("opensea_slug") == slug:
                cid = rec.get("collection_id")
                break
        if not cid and db_path:
            _, cid = _lookup_slug_in_db(db_path, chain, contract_lc, token_id)
        return {
            "collection_id": cid,
            "opensea_slug": slug,
            "resolution_source": "opensea-slug",
        }

    # --- 1b. Slug from overrides ---------------------------------------------
    ov_slug, ov_cid = _lookup_slug_in_overrides(
        overrides, chain, contract_lc, token_id
    )
    if ov_slug:
        return {
            "collection_id": ov_cid,
            "opensea_slug": ov_slug,
            "resolution_source": "override",
        }

    # --- 1c. Slug from collection_identifiers DB -----------------------------
    if db_path:
        db_slug, db_cid = _lookup_slug_in_db(
            db_path, chain, contract_lc, token_id
        )
        if db_slug:
            return {
                "collection_id": db_cid,
                "opensea_slug": db_slug,
                "resolution_source": "opensea-slug",
            }

    # --- Guard: shared storefront with no disambiguator ----------------------
    if contract_lc in shared_contracts and not token_id:
        raise ValueError(
            "Cannot resolve shared storefront collection by contract alone; "
            "token_id or slug required"
        )

    # --- 2. Contract + token ID via individual NFT lookup --------------------
    if token_id:
        nft_resp = await client.get_nft(chain, contract_lc, str(token_id))
        resolved_slug = _extract_collection_slug(nft_resp)
        if resolved_slug:
            return {
                "collection_id": None,
                "opensea_slug": resolved_slug,
                "resolution_source": "opensea-token",
            }
        # Could not read a slug from the NFT response — fall through to sweep
        # only if allowed, otherwise give up.
        if not allow_sweep:
            return {
                "collection_id": None,
                "opensea_slug": None,
                "resolution_source": "unresolved",
            }

    # --- 3. Contract sweep (opt-in) ------------------------------------------
    if allow_sweep:
        slug = await _sweep_contract(client, chain, contract_lc)
        if slug:
            return {
                "collection_id": None,
                "opensea_slug": slug,
                "resolution_source": "opensea-sweep",
            }

    return {
        "collection_id": None,
        "opensea_slug": None,
        "resolution_source": "unresolved",
    }


async def _sweep_contract(
    client: OpenSeaClient,
    chain: str,
    contract: str,
    max_pages: int = 50,
) -> Optional[str]:
    """Enumerate NFTs for a contract and return the most common collection slug."""
    cursor: Optional[str] = None
    counts: dict[str, int] = {}
    for _ in range(max_pages):
        resp = await client.get_contract_nfts(chain, contract, cursor)
        nfts = resp.get("nfts", []) if isinstance(resp, dict) else []
        for nft in nfts:
            col = nft.get("collection")
            if isinstance(col, str) and col:
                counts[col] = counts.get(col, 0) + 1
            elif isinstance(col, dict):
                s = col.get("slug")
                if isinstance(s, str) and s:
                    counts[s] = counts.get(s, 0) + 1
        cursor = resp.get("next") if isinstance(resp, dict) else None
        if not cursor:
            break
    if not counts:
        return None
    return max(counts, key=counts.get)


# --------------------------------------------------------------------------- persist


async def resolve_and_persist(
    client: OpenSeaClient,
    db_path: str | Path,
    chain: str,
    contract: str,
    token_id: Optional[str] = None,
    slug: Optional[str] = None,
    *,
    allow_sweep: bool = False,
) -> dict[str, Any]:
    """Resolve a collection and write the result to collection_identifiers."""
    result = await resolve(
        client,
        chain,
        contract,
        token_id=token_id,
        slug=slug,
        db_path=db_path,
        allow_sweep=allow_sweep,
    )
    os_slug = result.get("opensea_slug")
    if not os_slug:
        return result

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT OR IGNORE INTO collection_identifiers "
            "(collection_id, namespace, value, chain, contract, token_id, "
            " verified_at, resolution_source) "
            "VALUES (?, 'opensea_slug', ?, ?, ?, ?, ?, ?)",
            (
                result.get("collection_id"),
                os_slug,
                chain,
                contract.lower(),
                str(token_id) if token_id else None,
                now,
                result.get("resolution_source"),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return result


# --------------------------------------------------------------------------- CLI


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Resolve an OpenSea collection from chain/contract/token_id."
    )
    p.add_argument("--chain", default="ethereum", help="Blockchain identifier")
    p.add_argument("--contract", required=True, help="Contract address")
    p.add_argument("--token-id", dest="token_id", default=None, help="Token ID")
    p.add_argument("--slug", default=None, help="Known OpenSea slug")
    p.add_argument(
        "--db",
        default=str(_DEFAULT_DB),
        help="Path to vrm_index.db (default: data/vrm_index.db)",
    )
    p.add_argument(
        "--allow-sweep",
        dest="allow_sweep",
        action="store_true",
        help="Permit expensive contract-sweep resolution",
    )
    p.add_argument(
        "--persist",
        action="store_true",
        help="Write the resolved identifier to the collection_identifiers table",
    )
    return p


async def _amain(args: argparse.Namespace) -> int:
    async with OpenSeaClient() as client:
        if args.persist:
            result = await resolve_and_persist(
                client,
                args.db,
                args.chain,
                args.contract,
                token_id=args.token_id,
                slug=args.slug,
                allow_sweep=args.allow_sweep,
            )
        else:
            result = await resolve(
                client,
                args.chain,
                args.contract,
                token_id=args.token_id,
                slug=args.slug,
                db_path=args.db,
                allow_sweep=args.allow_sweep,
            )
    print(json.dumps(result, indent=2))
    return 0 if result.get("opensea_slug") else 1


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
