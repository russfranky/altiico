"""Export the catalog as a pre-alpha ``packages/avatars`` registry projection.

The downstream registry has a locked schema, so this exporter projects richer
catalog facts conservatively. Two distinctions are non-negotiable:

1. ownership chain and storage provider are independent;
2. IP/license rights and file-access gating are independent.

In particular, ``purchase_gated`` is derived only from explicit file-access
facts. A restrictive license never implies that downloading the file requires
owning the NFT.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.catalog_snapshot import record_snapshot, snapshot_created_at
except ModuleNotFoundError:
    from catalog_snapshot import record_snapshot, snapshot_created_at

REGISTRY_SCHEMA = "hubzz-avatars-registry-v1"
PREALPHA_CHAINS = {"ethereum", "zora", "polygon", "base", "optimism", "arbitrum"}
STORAGE_PROVIDERS = {"self-host", "ipfs", "arweave", "contract-metadata", "r2"}


def _norm(s: Any) -> str | None:
    if s is None:
        return None
    value = str(s).strip()
    return value or None


def _slug(row: dict[str, Any]) -> str:
    return row["id"]


def _chain(row: dict[str, Any]) -> tuple[str | None, str | None]:
    chain = (_norm(row.get("chain")) or "").lower()
    if chain in PREALPHA_CHAINS:
        return chain, None
    if not chain:
        return None, None
    if chain in {"arweave", "ipfs"}:
        return None, None
    return None, f"chain '{chain}' not in pre-alpha ChainSchema enum"


def _explicit_storage_types(row: dict[str, Any]) -> list[str]:
    raw = row.get("storage_types")
    if raw is None:
        return []
    if isinstance(raw, list):
        values = raw
    else:
        try:
            decoded = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            decoded = str(raw)
        values = decoded if isinstance(decoded, list) else [decoded]
    return sorted({str(item).strip().lower() for item in values if _norm(item)})


def _storage_provider(row: dict[str, Any]) -> str:
    """Project richer catalog storage into the locked pre-alpha enum."""
    explicit = _explicit_storage_types(row)
    if "ipfs" in explicit:
        return "ipfs"
    if "arweave" in explicit:
        return "arweave"
    if "onchain" in explicit:
        return "contract-metadata"
    if any(item in {"https", "holder_platform", "mixed"} for item in explicit):
        return "self-host"

    pattern = (_norm(row.get("vrm_url_pattern")) or "").lower()
    direct = (_norm(row.get("vrm_url_https")) or "").lower()
    chain = (_norm(row.get("chain")) or "").lower()
    combined = " ".join(part for part in (pattern, direct) if part)
    if pattern.startswith("ipfs://") or direct.startswith("ipfs://") or "/ipfs/" in combined:
        return "ipfs"
    if chain == "arweave" or "arweave" in combined or pattern.startswith("ar://") or direct.startswith("ar://"):
        return "arweave"
    if pattern or direct:
        return "self-host"
    if _norm(row.get("sample_metadata_url")) or _norm(row.get("vrm_param")):
        return "contract-metadata"
    return "self-host"


def _license_label(row: dict[str, Any]) -> str:
    vl = (
        (_norm(row.get("vrm_license")) or "")
        .upper()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )
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


def _explicit_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return None


def _purchase_gated(row: dict[str, Any]) -> bool:
    """Project explicit file ownership/access evidence to the locked bool.

    Unknown is represented as ``False`` only because the downstream schema has
    no nullable gating field. The strict catalog acceptance audit separately
    rejects unknown access, so this projection must never be treated as evidence.
    """
    explicit = _explicit_bool(row.get("file_access_requires_ownership"))
    if explicit is not None:
        return explicit
    mode = (_norm(row.get("file_access_mode")) or "").lower()
    if mode == "holder_gated":
        return True
    if mode in {"public", "unavailable"}:
        return False
    return False


def _avatar_count(row: dict[str, Any]) -> int | None:
    for key in ("avatar_count", "total_supply", "max_supply"):
        val = row.get(key)
        if isinstance(val, int) and val > 0:
            return val
        if isinstance(val, str) and val.strip().isdigit():
            return int(val.strip())
    return None


def _description(row: dict[str, Any]) -> str | None:
    return (
        _norm(row.get("short_description"))
        or _norm(row.get("curated_description"))
        or _norm(row.get("description"))
    )


def build_entry(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    chain, reason = _chain(row)
    entry: dict[str, Any] = {
        "slug": _slug(row),
        "name": _norm(row.get("name")) or _slug(row),
        "description": _description(row),
        "license": _license_label(row),
        "chain": chain,
        "storage_provider": _storage_provider(row),
        "contract": _norm(row.get("_canonical_contract")) or _norm(row.get("contract")),
        "banner": _norm(row.get("banner_image_url")),
        "pfp": _norm(row.get("image_url")) or _norm(row.get("sample_nft_image")),
        "avatar_count": _avatar_count(row),
        "purchase_gated": _purchase_gated(row),
        "status": "staged",
        "tier": _norm(row.get("tier")),
    }
    note = None
    if reason:
        note = {
            "slug": entry["slug"],
            "reason": reason,
            "original_chain": _norm(row.get("chain")),
        }
    return entry, note


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


def parse_tiers(raw: str) -> set[str]:
    tiers = {t.strip().upper() for t in raw.split(",") if t.strip()}
    invalid = tiers - {"A", "B", "C"}
    if invalid:
        raise SystemExit(
            f"invalid tier(s): {', '.join(sorted(invalid))} (allowed: A, B, C)"
        )
    return tiers


def build_registry(
    rows: list[dict[str, Any]],
    snapshot_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
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
        "generated_at": generated_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot_id": snapshot_id,
        "collections": entries,
        "unmapped": unmapped,
    }


def main(argv: Iterable[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Export avatars-registry.json for the pre-alpha packages/avatars ingest."
    )
    parser.add_argument("--db", default=str(repo_root / "data" / "vrm_index.db"))
    parser.add_argument(
        "--output", default=str(repo_root / "static" / "data" / "avatars-registry.json")
    )
    parser.add_argument("--tier", default="A,B", help="comma-separated tiers (default A,B)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"error: database not found at {db_path}", file=sys.stderr)
        return 1

    tiers = parse_tiers(args.tier)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        snapshot_id = record_snapshot(conn)
        generated_at = snapshot_created_at(conn, snapshot_id)
        rows = load_collections(conn, tiers)
        primary_contracts = (
            {
                str(item["collection_id"]): item["address"]
                for item in conn.execute(
                    """
                    SELECT collection_id, address
                    FROM contracts
                    WHERE is_primary=1
                    ORDER BY collection_id, rowid
                    """
                )
            }
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='contracts'"
            ).fetchone()
            else {}
        )
        for row in rows:
            row["_canonical_contract"] = primary_contracts.get(str(row["id"]))
    finally:
        conn.close()

    registry = build_registry(rows, snapshot_id, generated_at)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

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
