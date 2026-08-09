"""Export the catalog as a pre-alpha ``packages/avatars`` registry projection.

The pre-alpha Hubzz avatar backend (``packages/avatars``) owns a locked
canonical schema (``packages/avatars/schema/src/avatar.ts``, SCHEMA_VERSION 1).
Its registry (`collections/index.json` on R2, seeded by
``seed-registry.ts``) carries one row per avatar SET. Today that seed is 8
hardcoded collections; this catalog is the authoritative superset that can
regenerate it from real data.

This exporter emits ``static/data/avatars-registry.json`` in that registry
shape so the pre-alpha ``avatar-api`` can ingest it. It deliberately obeys the
pre-alpha schema's two locked design rules:

  1. CHAIN and STORAGE are orthogonal. ``chain`` is the OWNERSHIP blockchain and
     is one of a fixed enum (or null for CC0 / non-NFT sets). ``arweave`` and
     ``ipfs`` are STORAGE providers, never chains — the pre-alpha schema calls
     ``chain: a.chain || source`` "the bug in the current API". We split them.
  2. Chains outside the pre-alpha enum (shape, ape_chain, solana, "multi") are
     NOT coerced. The collection still ships with ``chain: null`` and is listed
     under ``unmapped`` with a reason, so a human decides — we never invent a
     chain the downstream enum cannot represent.

Nothing here mutates the DB or touches pre-alpha; it only writes one JSON file.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REGISTRY_SCHEMA = "hubzz-avatars-registry-v1"

# The pre-alpha ChainSchema enum (packages/avatars/schema/src/avatar.ts).
# A catalog chain NOT in this set becomes null + an `unmapped` note.
PREALPHA_CHAINS = {"ethereum", "zora", "polygon", "base", "optimism", "arbitrum"}

# The pre-alpha StorageProviderSchema enum.
STORAGE_PROVIDERS = {"self-host", "ipfs", "arweave", "contract-metadata", "r2"}

# Catalog license terms -> the string form the registry seed uses
# (seed-registry.ts values: "CC0", "CC-BY", "All Rights Reserved", ...).
LICENSE_OPEN = "open"        # redistribution allowed, no holder gate
LICENSE_RESTRICTED = "restricted"  # holder-gated / redistribution prohibited


def _norm(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.strip()
    return s or None


def _slug(row: dict[str, Any]) -> str:
    """The set slug. The catalog collection id already serves this role."""
    return row["id"]


def _chain(row: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (chain_or_none, unmapped_reason_or_none) per locked rule 1/2."""
    chain = (_norm(row.get("chain")) or "").lower()
    if chain in PREALPHA_CHAINS:
        return chain, None
    if not chain:
        return None, None  # CC0 / non-NFT sets legitimately have no chain
    # A storage provider mis-filed in the chain column (rule 1's exact bug):
    # null the chain, let _storage_provider pick it up, do NOT flag as unmapped.
    if chain in {"arweave", "ipfs"}:
        return None, None
    # A real chain the downstream enum cannot represent — do not coerce.
    return None, f"chain '{chain}' not in pre-alpha ChainSchema enum"


def _storage_provider(row: dict[str, Any]) -> str:
    """Where the ORIGINAL asset is hosted — orthogonal to chain (rule 1)."""
    pattern = (_norm(row.get("vrm_url_pattern")) or "").lower()
    chain = (_norm(row.get("chain")) or "").lower()
    if pattern.startswith("ipfs://") or "/ipfs/" in pattern:
        return "ipfs"
    if chain == "arweave" or "arweave" in pattern or pattern.startswith("ar://"):
        return "arweave"
    # Any other non-empty pattern is a direct file host (catalog patterns are
    # often scheme-less, e.g. "nft.retrodoges.com/main/vrm/{id}.vrm").
    if pattern:
        return "self-host"
    # No direct file pattern: the VRM is only reachable via token metadata.
    if _norm(row.get("sample_metadata_url")) or _norm(row.get("vrm_param")):
        return "contract-metadata"
    return "self-host"


def _license_label(row: dict[str, Any]) -> str:
    """Human-facing license string, mirroring the seed-registry vocabulary."""
    vl = (_norm(row.get("vrm_license")) or "").upper().replace(" ", "").replace("-", "").replace("_", "")
    if vl.startswith("CC0") or "PUBLICDOMAIN" in vl:
        return "CC0"
    if vl.startswith("CCBYNCND"):
        return "CC-BY-NC-ND"
    if vl.startswith("CCBYNCSA"):
        return "CC-BY-NC-SA"
    if vl.startswith("CCBYNC"):
        return "CC-BY-NC"
    if vl.startswith("CCBYSA"):
        return "CC-BY-SA"
    if vl.startswith("CCBYND"):
        return "CC-BY-ND"
    if vl.startswith("CCBY"):
        return "CC-BY"
    if "REDISTRIBUTIONPROHIBITED" in vl or "ALLRIGHTSRESERVED" in vl:
        return "All Rights Reserved"
    return "Unknown"


def _purchase_gated(row: dict[str, Any]) -> bool:
    """Whether the set requires owning the NFT (pre-alpha `purchase_gated`).

    The pre-alpha server treats gating as "an economics rule, not a security
    boundary" and fails OPEN, so we gate only when the catalog clearly says the
    license is holder-restricted or redistribution-prohibited. Open (CC0/CC-BY)
    and unknown default to ungated, matching the seed-registry's mostly-open set.
    """
    category = (_norm(row.get("license_category")) or "").lower()
    allowed_user = (_norm(row.get("allowed_user")) or "").lower()
    redistribution = (_norm(row.get("redistribution")) or "").lower()
    label = _license_label(row)
    if category == "red":
        return True
    if label == "All Rights Reserved":
        return True
    if allowed_user == "holder":
        return True
    if redistribution == "prohibited":
        return True
    return False


def _avatar_count(row: dict[str, Any]) -> int | None:
    for key in ("avatar_count", "total_supply", "max_supply"):
        val = row.get(key)
        if isinstance(val, int) and val > 0:
            return val
        if isinstance(val, str) and val.strip().isdigit():
            return int(val.strip())
    return None


def build_entry(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return (registry_entry, unmapped_note_or_none)."""
    chain, reason = _chain(row)
    entry: dict[str, Any] = {
        "slug": _slug(row),
        "name": _norm(row.get("name")) or _slug(row),
        "description": _norm(row.get("description")),
        "license": _license_label(row),
        "chain": chain,
        "storage_provider": _storage_provider(row),
        "contract": _norm(row.get("contract")),
        "banner": _norm(row.get("banner_image_url")),
        "pfp": _norm(row.get("image_url")) or _norm(row.get("sample_nft_image")),
        "avatar_count": _avatar_count(row),
        "purchase_gated": _purchase_gated(row),
        "status": "staged",  # catalog data is not yet published to R2
        "tier": _norm(row.get("tier")),
    }
    note = None
    if reason:
        note = {"slug": entry["slug"], "reason": reason,
                "original_chain": _norm(row.get("chain"))}
    return entry, note


# ─── DB access ───────────────────────────────────────────────────────────────


def _row_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def load_collections(conn: sqlite3.Connection, tiers: set[str]) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in tiers)
    cur = conn.execute(
        f"SELECT * FROM collections WHERE tier IN ({placeholders}) ORDER BY tier ASC, name ASC",
        tuple(tiers),
    )
    cur.row_factory = _row_factory  # type: ignore[assignment]
    return list(cur.fetchall())


# ─── main ────────────────────────────────────────────────────────────────────


def parse_tiers(raw: str) -> set[str]:
    tiers = {t.strip().upper() for t in raw.split(",") if t.strip()}
    invalid = tiers - {"A", "B", "C"}
    if invalid:
        raise SystemExit(f"invalid tier(s): {', '.join(sorted(invalid))} (allowed: A, B, C)")
    return tiers


def build_registry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    for row in rows:
        entry, note = build_entry(row)
        entries.append(entry)
        if note:
            unmapped.append(note)
    return {
        "schema": REGISTRY_SCHEMA,
        "source": "vrm-catalog",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "collections": entries,
        "unmapped": unmapped,
    }


def main(argv: Iterable[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Export avatars-registry.json for the pre-alpha packages/avatars ingest."
    )
    parser.add_argument("--db", default=str(repo_root / "data" / "vrm_index.db"))
    parser.add_argument("--output", default=str(repo_root / "static" / "data" / "avatars-registry.json"))
    parser.add_argument("--tier", default="A,B", help="comma-separated tiers (default A,B)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"error: database not found at {db_path}", file=sys.stderr)
        return 1

    tiers = parse_tiers(args.tier)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = load_collections(conn, tiers)
    finally:
        conn.close()

    registry = build_registry(rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    gated = sum(1 for c in registry["collections"] if c["purchase_gated"])
    with_chain = sum(1 for c in registry["collections"] if c["chain"])
    print(
        f"wrote {output_path} ({len(registry['collections'])} sets; "
        f"{with_chain} with a mapped chain; {gated} purchase-gated; "
        f"{len(registry['unmapped'])} unmapped chains)",
        file=sys.stderr,
    )
    for note in registry["unmapped"]:
        print(f"  unmapped: {note['slug']} — {note['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
