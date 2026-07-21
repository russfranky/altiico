#!/usr/bin/env python3
"""Emit content-hashed JSON data files for the VRM catalog from vrm_index.db.

Reads the SQLite database produced by build_index.py and writes sharded,
content-hashed JSON files to static/data/. A build-info.json manifest maps
logical names to the current hashed filenames so the frontend can load them
with cache-busting URLs.

Outputs (in --output-dir, default static/data):
  - catalog-summary.{hash}.json   — stats + filter options
  - collections.{hash}.json        — 74 collection records with contracts joined
  - opensea-candidates.{hash}.json — 216 OpenSea candidate records
  - avatars-00.{hash}.json …       — avatars sharded by 500 rows each
  - build-info.json                — unhashed manifest pointing to hashed files

Usage:
  python scripts/build_catalog.py [--db data/vrm_index.db] [--output-dir static/data]
"""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
DEFAULT_DB = BASE / "data" / "vrm_index.db"
DEFAULT_OUTPUT = BASE / "static" / "data"

AVATAR_SHARD_SIZE = 500
SCHEMA_VERSION = 1


def hash_content(content_bytes: bytes) -> str:
    """Return first 12 hex chars of SHA-256 over the file content."""
    return hashlib.sha256(content_bytes).hexdigest()[:12]


def write_hashed(output_dir: Path, logical_name: str, data: dict) -> str:
    """Serialize data to compact JSON, hash it, write to output_dir.

    Returns the hashed filename (e.g. 'collections.a1b2c3d4e5f6.json').
    """
    content = json.dumps(data, separators=(",", ":")).encode("utf-8")
    h = hash_content(content)
    filename = f"{logical_name}.{h}.json"
    (output_dir / filename).write_bytes(content)
    return filename


def query_collections(conn) -> list:
    """Query all collections with contracts joined."""
    collections = [dict(r) for r in conn.execute(
        "SELECT * FROM collections ORDER BY name"
    )]

    # Load all contracts grouped by collection_id
    contracts_map: dict[str, list] = {}
    for r in conn.execute(
        "SELECT collection_id, address, chain, is_primary "
        "FROM contracts ORDER BY is_primary DESC, chain"
    ):
        cid = r["collection_id"]
        if cid not in contracts_map:
            contracts_map[cid] = []
        contracts_map[cid].append({
            "address": r["address"],
            "chain": r["chain"],
            "is_primary": r["is_primary"],
        })

    for c in collections:
        c["contracts"] = contracts_map.get(c["id"], [])

    return collections


def query_opensea_candidates(conn) -> list:
    """Query all OpenSea candidates."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM opensea_candidates ORDER BY slug"
    )]


def query_avatars(conn) -> list:
    """Query all avatars (subset of columns matching original build_html)."""
    return [dict(r) for r in conn.execute(
        "SELECT id, collection_id, name, description, "
        "model_file_url, format, thumbnail_url "
        "FROM avatars ORDER BY collection_id, name"
    )]


def build_summary(conn, collections, avatars, opensea) -> dict:
    """Build the catalog-summary object with stats and filter options."""
    # Tier counts
    tiers: dict[str, int] = {}
    for c in collections:
        t = c.get("tier") or "unknown"
        tiers[t] = tiers.get(t, 0) + 1

    # Distinct chains and licenses
    chains = sorted({c.get("chain") for c in collections if c.get("chain")})
    licenses = sorted(
        {c.get("license_category") or "unknown" for c in collections}
    )

    # UI stats (matching the original inline stats init)
    stats = {
        "collections": len(collections),
        "avatars": len(avatars),
        "os": len(opensea),
        "green": sum(1 for c in collections if c.get("license_category") == "green"),
        "yellow": sum(1 for c in collections if c.get("license_category") == "yellow"),
        "red": sum(1 for c in collections if c.get("license_category") == "red"),
        "alive": sum(1 for c in opensea if c.get("url_status") == "alive"),
        "dead": sum(1 for c in opensea if c.get("url_status") == "dead"),
        "wayback": sum(1 for c in opensea if c.get("wayback_available")),
        "dc_alive": sum(1 for c in opensea if c.get("discord_status") == "alive"),
        "dc_dead": sum(1 for c in opensea if c.get("discord_status") == "dead"),
        "capped": sum(
            1 for c in collections
            if c.get("mint_status") in ("capped", "likely_capped")
        ),
        "ongoing": sum(1 for c in collections if c.get("mint_status") == "ongoing"),
    }

    return {
        "total_collections": len(collections),
        "total_avatars": len(avatars),
        "total_candidates": len(opensea),
        "tiers": tiers,
        "chains": chains,
        "licenses": licenses,
        "stats": stats,
    }


def shard_avatars(avatars: list, shard_size: int) -> list[list]:
    """Split avatars into shards of at most shard_size rows each."""
    return [
        avatars[i : i + shard_size]
        for i in range(0, len(avatars), shard_size)
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Emit content-hashed JSON data files for the VRM catalog."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="Path to vrm_index.db (default: data/vrm_index.db)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory (default: static/data)",
    )
    args = parser.parse_args()

    db_path = args.db.resolve()
    output_dir = args.output_dir.resolve()

    if not db_path.exists():
        print(f"Error: database not found at {db_path}")
        print("Run scripts/build_index.py first to generate vrm_index.db.")
        raise SystemExit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    print("Querying database...")
    collections = query_collections(conn)
    opensea = query_opensea_candidates(conn)
    avatars = query_avatars(conn)
    conn.close()

    print(f"  Collections: {len(collections)}")
    print(f"  Avatars: {len(avatars)}")
    print(f"  OpenSea candidates: {len(opensea)}")

    # Build summary
    summary = build_summary(conn, collections, avatars, opensea)

    # Write hashed files
    print("Writing hashed JSON files...")
    files: dict[str, str] = {}

    files["summary"] = write_hashed(output_dir, "catalog-summary", summary)
    print(f"  {files['summary']}")

    files["collections"] = write_hashed(
        output_dir, "collections", {"collections": collections}
    )
    print(f"  {files['collections']}")

    files["opensea"] = write_hashed(
        output_dir, "opensea-candidates", {"candidates": opensea}
    )
    print(f"  {files['opensea']}")

    # Shard avatars
    shards = shard_avatars(avatars, AVATAR_SHARD_SIZE)
    avatar_files = []
    for i, shard in enumerate(shards):
        logical = f"avatars-{i:02d}"
        fname = write_hashed(output_dir, logical, {"avatars": shard})
        avatar_files.append(fname)
        print(f"  {fname}  ({len(shard)} avatars)")
    files["avatars"] = avatar_files

    # Write build-info.json (unhashed, short TTL)
    build_info = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "files": files,
    }
    build_info_path = output_dir / "build-info.json"
    build_info_path.write_text(
        json.dumps(build_info, indent=2), encoding="utf-8"
    )
    print(f"  build-info.json")

    total_size = sum(
        f.stat().st_size for f in output_dir.glob("*.json")
    )
    print(f"\nDone. {len(list(output_dir.glob('*.json')))} files, "
          f"{total_size // 1024}KB total in {output_dir}")


if __name__ == "__main__":
    main()
