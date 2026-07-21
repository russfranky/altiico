"""Export a declarative avatar-manifest-v1.json for hubzz to resolve VRM URLs generically, replacing the RetroDoges-specific resolver."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MANIFEST_SCHEMA_URL = "https://superyeti.example/schema/avatar-manifest-v1.schema.json"
MANIFEST_VERSION = "1.0.0"
SCHEMA_PATH = "static/schema/avatar-manifest-v1.schema.json"

# CAIP-19 style chain-id prefixes keyed by superyeti chain name.
CHAIN_ID_MAP = {
    "ethereum": "1",
    "mainnet": "1",
    "base": "8453",
    "optimism": "10",
    "polygon": "137",
    "shape": "360",
    "arbitrum": "42161",
    "solana": "solana",
    "arweave": "arweave",
}

# token_standard values in the contracts table -> CAIP asset namespace.
STANDARD_MAP = {
    "erc721": "erc721",
    "erc-721": "erc721",
    "erc1155": "erc1155",
    "erc-1155": "erc1155",
    "erc721a": "erc721",
    "erc-721a": "erc721",
}

# Default JSON pointer candidates for token_metadata resolution.
DEFAULT_VRM_POINTER_CANDIDATES = [
    "/vrm_url",
    "/vrm",
    "/asset",
    "/animation_url",
    "/files/0/uri",
]

# Token-id placeholders we recognise in vrm_url_pattern / metadata templates.
TOKEN_PLACEHOLDER_RE = re.compile(r"\{token_id\}|\{id\}|\{token\}|%d|%\d+d", re.IGNORECASE)


# ─── helpers ─────────────────────────────────────────────────────────────────


def _norm(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.strip()
    return s or None


def _chain_id(chain: str | None) -> str | None:
    if not chain:
        return None
    return CHAIN_ID_MAP.get(chain.lower(), CHAIN_ID_MAP.get(chain.lower().split()[0]))


def _standard(token_standard: str | None) -> str:
    if not token_standard:
        return "erc721"
    key = token_standard.lower().replace(" ", "")
    return STANDARD_MAP.get(key, token_standard.lower())


def _caip_id(chain: str | None, token_standard: str | None, contract: str | None,
             is_erc1155_shared: bool = False) -> str | None:
    """Build a CAIP-19-style asset id, e.g. eip155:1/erc721:0xabc...

    Non-EVM chains (solana, arweave) map to non-numeric chain ids and do not
    fit the eip155 namespace; return None so the caller falls back to the
    superyeti collection slug id. The schema's id pattern requires a numeric
    chain reference after ``eip155:``, so emitting ``eip155:solana/...`` would
    fail validation.
    """
    if not contract:
        return None
    cid = _chain_id(chain)
    if cid is None:
        return None
    if not cid.isdigit():
        return None
    ns = _standard(token_standard)
    asset = f"eip155:{cid}/{ns}:{contract}"
    if is_erc1155_shared:
        asset += "/token_id"
    return asset


def _has_token_placeholder(pattern: str | None) -> bool:
    if not pattern:
        return False
    return bool(TOKEN_PLACEHOLDER_RE.search(pattern))


# ─── license mapping ─────────────────────────────────────────────────────────


def build_license(row: dict[str, Any]) -> dict[str, Any]:
    """Map collections.license_category + vrm_license + commercial_use +
    allowed_user + redistribution to the License schema dimensions.

    Conservative defaults: when data is missing or ambiguous, prefer the more
    restrictive / unknown option rather than granting rights the source did not
    clearly grant.
    """
    license_category = _norm(row.get("license_category"))
    vrm_license = _norm(row.get("vrm_license"))
    commercial_use = _norm(row.get("commercial_use"))
    allowed_user = _norm(row.get("allowed_user"))
    redistribution = _norm(row.get("redistribution"))

    # --- use_scope ---
    use_scope = "unknown"
    au = (allowed_user or "").lower()
    if au in ("everyone", "everybody"):
        use_scope = "everyone"
    elif au.startswith("explicitly"):
        use_scope = "explicitly_licensed"
    elif au.startswith("onlyauthor") or au == "author":
        use_scope = "author"
    elif au == "holder":
        use_scope = "holder"

    # --- commercial_scope ---
    commercial_scope = "unknown"
    cu = (commercial_use or "").lower()
    if cu == "allow":
        if license_category == "green":
            commercial_scope = "corporation"
        else:
            commercial_scope = "personal_profit"
    elif cu == "disallow":
        commercial_scope = "none"

    # --- credit ---
    credit = "unknown"
    vl = (vrm_license or "").upper().replace(" ", "").replace("-", "")
    if vl in ("CCBY", "CCBYSA", "CCBYNC", "CCBYNCSA", "CCBYND", "CCBYNCND"):
        credit = "required"
    elif vl in ("CC0", "PUBLICDOMAIN", "PUBLICDOMAINMARK"):
        credit = "unnecessary"
    elif vl in ("CCBY",):
        credit = "required"

    # --- booleans (conservative: false unless explicitly allowed) ---
    redistribute_original = False
    rd = (redistribution or "").lower()
    if rd == "allow":
        redistribute_original = True
    elif rd == "prohibited":
        redistribute_original = False

    # Modify: green category or CC0/CC-BY implies modifiable; red prohibits.
    modify = False
    if license_category == "green":
        modify = True
    elif license_category == "red":
        modify = False
    elif vl in ("CC0", "CCBY", "CCBYSA", "PUBLICDOMAIN", "PUBLICDOMAINMARK"):
        modify = True
    elif vl in ("CCBYND", "CCBYNCND", "NOMODIFY", "MODIFICATIONPROHIBITED"):
        modify = False

    redistribute_modified = modify and redistribute_original
    corporate_use = commercial_scope == "corporation"
    terminates_on_transfer = use_scope == "holder"
    hate_speech_termination = license_category in ("green", "yellow")

    return {
        "use_scope": use_scope,
        "commercial_scope": commercial_scope,
        "credit": credit,
        "redistribute_original": redistribute_original,
        "modify": modify,
        "redistribute_modified": redistribute_modified,
        "corporate_use": corporate_use,
        "terminates_on_transfer": terminates_on_transfer,
        "hate_speech_termination": hate_speech_termination,
    }


# ─── resolution ──────────────────────────────────────────────────────────────


def build_resolution(row: dict[str, Any]) -> dict[str, Any]:
    """Determine the resolution strategy from collection fields."""
    vrm_url_pattern = _norm(row.get("vrm_url_pattern"))
    vrm_param = _norm(row.get("vrm_param"))
    sample_metadata_url = _norm(row.get("sample_metadata_url"))

    # 1. url_template: pattern with a token-id placeholder.
    if vrm_url_pattern and _has_token_placeholder(vrm_url_pattern):
        return {
            "strategy": "url_template",
            "template": vrm_url_pattern,
        }

    # 2. token_metadata: we have a sample metadata URL to follow.
    if sample_metadata_url:
        template = sample_metadata_url
        # Normalise a concrete sample URL into a template if it carries a token id.
        template = re.sub(r"/\d+(?:/metadata(?:\.json)?)?$", "/{token_id}/metadata.json", template)
        template = re.sub(r"/\d+\.json$", "/{token_id}.json", template)
        return {
            "strategy": "token_metadata",
            "metadata_url": {"template": template},
            "vrm_pointer": {
                "json_pointer_candidates": list(DEFAULT_VRM_POINTER_CANDIDATES),
                "required_mime": ["model/gltf-binary", "model/vrm", "application/octet-stream"],
            },
        }

    # 3. vrm_param set but no pattern: still token_metadata (hubzz fetches
    #    per-token metadata and extracts the named field).
    if vrm_param:
        return {
            "strategy": "token_metadata",
            "vrm_pointer": {
                "json_pointer_candidates": list(DEFAULT_VRM_POINTER_CANDIDATES),
                "required_mime": ["model/gltf-binary", "model/vrm", "application/octet-stream"],
            },
        }

    # 4. Nothing usable.
    return {"strategy": "unavailable"}


# ─── identifiers ─────────────────────────────────────────────────────────────


def build_identifiers(row: dict[str, Any], ci_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Assemble the identifiers object from the collections row plus
    collection_identifiers rows."""
    identifiers: dict[str, Any] = {}
    chain = _norm(row.get("chain"))
    if chain:
        identifiers["chain"] = chain
    cid = _chain_id(chain)
    if cid:
        identifiers["chain_id"] = cid

    # Prefer a contract_token identifier row, fall back to collections.contract.
    contract = None
    standard = None
    for ci in ci_rows:
        if ci["namespace"] == "contract_token" and ci.get("contract"):
            contract = ci["contract"]
            break
    if not contract:
        contract = _norm(row.get("contract"))
    if contract:
        identifiers["contract"] = contract

    # token_standard from contracts table isn't in the row; infer from id pattern.
    # (The caller may pass it via ci_rows metadata_url; we leave standard optional.)
    for ci in ci_rows:
        if ci["namespace"] == "contract_token" and ci.get("value"):
            # We can't reliably infer standard here; skip unless provided.
            break

    opensea_slug = None
    for ci in ci_rows:
        if ci["namespace"] == "opensea_slug" and ci.get("value"):
            opensea_slug = ci["value"]
            break
    if not opensea_slug:
        opensea_slug = _norm(row.get("opensea_slug"))
    if opensea_slug:
        identifiers["opensea_slug"] = opensea_slug

    return identifiers


# ─── collection entry ────────────────────────────────────────────────────────


def build_collection(
    row: dict[str, Any],
    ci_rows: list[dict[str, Any]],
    contract_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    tier = _norm(row.get("tier"))
    if tier not in ("A", "B", "C"):
        return None

    chain = _norm(row.get("chain"))

    # Determine primary contract + standard.
    primary_contract = _norm(row.get("contract"))
    token_standard = "erc721"
    is_erc1155_shared = False
    for c in contract_rows:
        if c.get("is_primary"):
            primary_contract = c["address"]
            token_standard = _norm(c.get("token_standard")) or token_standard
            break
    if not primary_contract and contract_rows:
        primary_contract = contract_rows[0]["address"]
        token_standard = _norm(contract_rows[0].get("token_standard")) or token_standard

    # ERC-1155 shared storefront contracts (e.g. 0x495f...) need /token_id.
    std = _standard(token_standard)
    if std == "erc1155":
        is_erc1155_shared = True

    caip = _caip_id(chain, token_standard, primary_contract, is_erc1155_shared)
    if not caip:
        # Fall back to the superyeti collection id if we can't build a CAIP id.
        caip = row["id"]

    entry: dict[str, Any] = {
        "id": caip,
        "name": row["name"],
        "tier": tier,
        "identifiers": build_identifiers(row, ci_rows),
        "resolution": build_resolution(row),
    }

    license_obj = build_license(row)
    entry["license"] = license_obj

    return entry


# ─── DB access ───────────────────────────────────────────────────────────────


def _row_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def load_collections(conn: sqlite3.Connection, tiers: set[str]) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in tiers)
    sql = f"""
        SELECT * FROM collections
        WHERE tier IN ({placeholders})
        ORDER BY tier ASC, name ASC
    """
    cur = conn.execute(sql, tuple(tiers))
    cur.row_factory = _row_factory  # type: ignore[assignment]
    return list(cur.fetchall())


def load_identifiers(conn: sqlite3.Connection, collection_id: str) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM collection_identifiers WHERE collection_id = ?",
        (collection_id,),
    )
    cur.row_factory = _row_factory  # type: ignore[assignment]
    return list(cur.fetchall())


def load_contracts(conn: sqlite3.Connection, collection_id: str) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM contracts WHERE collection_id = ? ORDER BY is_primary DESC",
        (collection_id,),
    )
    cur.row_factory = _row_factory  # type: ignore[assignment]
    return list(cur.fetchall())


# ─── token maps ──────────────────────────────────────────────────────────────


def write_token_maps(collections: list[dict[str, Any]], maps_dir: Path) -> list[dict[str, Any]]:
    """If any collection uses token_map strategy, split its map into a sidecar
    JSON file under maps_dir and point resolution.map_url at it.

    Currently no collection is expected to use token_map, but the code path is
    here for completeness.
    """
    maps_dir.mkdir(parents=True, exist_ok=True)
    updated: list[dict[str, Any]] = []
    for c in collections:
        res = c.get("resolution", {})
        if res.get("strategy") != "token_map":
            updated.append(c)
            continue
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", c["id"])
        map_path = maps_dir / f"{safe_id}.json"
        # token_map payload would come from the DB; placeholder empty map.
        map_data: dict[str, Any] = {"collection_id": c["id"], "tokens": {}}
        map_path.write_text(json.dumps(map_data, indent=2) + "\n", encoding="utf-8")
        res["map_url"] = str(map_path.relative_to(maps_dir.parent.parent))
        updated.append(c)
    return updated


# ─── validation ──────────────────────────────────────────────────────────────


def validate_manifest(manifest: dict[str, Any], schema_path: Path) -> bool:
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError:
        print(
            "warning: jsonschema library not installed; skipping validation.",
            file=sys.stderr,
        )
        return False
    if not schema_path.exists():
        print(f"warning: schema file not found at {schema_path}; skipping validation.",
              file=sys.stderr)
        return False
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=manifest, schema=schema)
    except jsonschema.ValidationError as exc:  # type: ignore[attr-defined]
        print(f"validation error: {exc.message}\n  at: {'/'.join(str(p) for p in exc.absolute_path)}",
              file=sys.stderr)
        return False
    print("validation: OK", file=sys.stderr)
    return True


# ─── main ────────────────────────────────────────────────────────────────────


def parse_tiers(raw: str) -> set[str]:
    tiers = {t.strip().upper() for t in raw.split(",") if t.strip()}
    invalid = tiers - {"A", "B", "C"}
    if invalid:
        raise SystemExit(f"invalid tier(s): {', '.join(sorted(invalid))} (allowed: A, B, C)")
    return tiers


def main(argv: Iterable[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Export avatar-manifest-v1.json for hubzz."
    )
    parser.add_argument("--db", default=str(repo_root / "data" / "vrm_index.db"),
                        help="path to vrm_index.db (default: data/vrm_index.db)")
    parser.add_argument("--output", default=str(repo_root / "static" / "data" / "avatar-manifest-v1.json"),
                        help="output manifest path")
    parser.add_argument("--tier", default="A,B",
                        help="comma-separated tiers to include (A, B, C). Default: A,B")
    parser.add_argument("--validate", action="store_true",
                        help="validate output against the JSON schema (requires jsonschema)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"error: database not found at {db_path}", file=sys.stderr)
        return 1

    tiers = parse_tiers(args.tier)
    output_path = Path(args.output)
    maps_dir = output_path.parent / "maps"

    conn = sqlite3.connect(str(db_path))
    try:
        rows = load_collections(conn, tiers)
        collections: list[dict[str, Any]] = []
        for row in rows:
            ci_rows = load_identifiers(conn, row["id"])
            contract_rows = load_contracts(conn, row["id"])
            entry = build_collection(row, ci_rows, contract_rows)
            if entry is not None:
                collections.append(entry)
    finally:
        conn.close()

    collections = write_token_maps(collections, maps_dir)

    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA_URL,
        "version": MANIFEST_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "collections": collections,
    }

    if args.validate:
        schema_path = repo_root / SCHEMA_PATH
        validate_manifest(manifest, schema_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"wrote {output_path} ({len(collections)} collections)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
