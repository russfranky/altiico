#!/usr/bin/env python3
"""Emit content-hashed JSON data files for the VRM catalog from vrm_index.db.

Reads the SQLite database produced by build_index.py and writes a
content-hashed collections file to static/data/. A build-info.json manifest
maps logical names to the current hashed filename so the frontend can load it
with a cache-busting URL.

Outputs (in --output-dir, default static/data):
  - collections.{hash}.json — collection records with contracts joined
  - build-info.json         — unhashed manifest pointing to the hashed file

Usage:
  python scripts/build_catalog.py [--db data/vrm_index.db] [--output-dir static/data]
"""
import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.catalog_snapshot import record_snapshot, snapshot_created_at
    from scripts.sanitize_staging_provenance import sanitize_staging_provenance
except ModuleNotFoundError:  # direct `python scripts/build_catalog.py` execution
    from catalog_snapshot import record_snapshot, snapshot_created_at
    from sanitize_staging_provenance import sanitize_staging_provenance

BASE = Path(__file__).parent.parent
DEFAULT_DB = BASE / "data" / "vrm_index.db"
DEFAULT_OUTPUT = BASE / "static" / "data"

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
    """Query all collections with contracts and license dimensions joined."""
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

    # Load license dimensions for enrichment of the license badge
    license_map: dict[str, dict] = {}
    for r in conn.execute(
        "SELECT collection_id, color, reason_codes, confidence, "
        "use_scope, commercial_scope, credit, "
        "redistribute_original, modify, redistribute_modified "
        "FROM license_dimensions"
    ):
        cid = r["collection_id"]
        import json as _json
        reason_codes = []
        raw_rc = r["reason_codes"]
        if raw_rc:
            try:
                reason_codes = _json.loads(raw_rc)
            except (ValueError, TypeError):
                reason_codes = []
        license_map[cid] = {
            "license_color": r["color"],
            "reason_codes": reason_codes,
            "license_confidence": r["confidence"],
            "use_scope": r["use_scope"],
            "commercial_scope": r["commercial_scope"],
            "credit": r["credit"],
            "redistribute_original": r["redistribute_original"],
            "modify": r["modify"],
            "redistribute_modified": r["redistribute_modified"],
        }

    # Roll per-avatar reachability up to the collection: the research question is
    # "are this collection's files reachable", not "browse 4,274 avatars".
    avatar_reach: dict[str, dict] = {}
    for r in conn.execute(
        "SELECT collection_id, COUNT(*) n, "
        "SUM(CASE WHEN reachable=1 THEN 1 ELSE 0 END) ok, "
        "SUM(CASE WHEN reachable=0 THEN 1 ELSE 0 END) bad "
        "FROM avatars GROUP BY collection_id"
    ):
        avatar_reach[r["collection_id"]] = {
            "avatars_total": r["n"], "avatars_reachable": r["ok"], "avatars_dead": r["bad"],
        }

    for c in collections:
        c.pop("project_status", None)
        c["contracts"] = contracts_map.get(c["id"], [])
        c.update(avatar_reach.get(c["id"], {}))
        ld = license_map.get(c["id"])
        if ld:
            c.update(ld)

    return collections


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

    provenance = sanitize_staging_provenance(output_dir)
    if provenance["setsSanitized"] or provenance["sidecarFieldsSanitized"]:
        print(
            "Sanitized collection-level staging provenance: "
            f"{provenance['setsSanitized']} set(s), "
            f"{provenance['sidecarFieldsSanitized']} sidecar field(s)"
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    print("Querying database...")
    snapshot_id = record_snapshot(conn)
    generated_at = snapshot_created_at(conn, snapshot_id)
    collections = query_collections(conn)
    conn.close()

    print(f"  Collections: {len(collections)}")

    # Write hashed files
    print("Writing hashed JSON files...")
    files: dict[str, str] = {}

    files["collections"] = write_hashed(
        output_dir, "collections", {"snapshot_id": snapshot_id, "collections": collections}
    )
    print(f"  {files['collections']}")

    # Write build-info.json (unhashed, short TTL)
    # Preserve market_data_as_of from enrich_opensea.py if a prior build-info
    # exists — enrich_opensea.py writes it, and build_catalog.py must not
    # drop it when regenerating the file list.
    build_info_path = output_dir / "build-info.json"
    prior_market_data_as_of = None
    if build_info_path.exists():
        try:
            prior = json.loads(build_info_path.read_text(encoding="utf-8"))
            prior_market_data_as_of = prior.get("market_data_as_of")
        except (json.JSONDecodeError, OSError):
            pass

    build_info = {
        "generated_at": generated_at,
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "files": files,
    }
    if prior_market_data_as_of:
        build_info["market_data_as_of"] = prior_market_data_as_of
    build_info_path.write_text(
        json.dumps(build_info, indent=2), encoding="utf-8"
    )

    # Stamp the service-worker cache version with this build's identity.
    # Without this the SW kept serving a stale app shell and shipped UI changes
    # were invisible to anyone who had visited before.
    sw_path = output_dir.parent / "sw.js"
    if sw_path.exists():
        sw = sw_path.read_text(encoding="utf-8")
        # Hash the DATA manifest *and* the app shell — a UI-only change must
        # invalidate the cache too, which is the case that originally broke.
        shell = b"".join((output_dir.parent / f).read_bytes()
                         for f in ("index.html", "app.js", "app.css")
                         if (output_dir.parent / f).exists())
        stamp = hash_content(json.dumps(files, sort_keys=True).encode("utf-8") + shell)
        sw_new = re.sub(r"const CACHE_VERSION = '[^']*';",
                        f"const CACHE_VERSION = '{stamp}';", sw, count=1)
        if sw_new != sw:
            sw_path.write_text(sw_new, encoding="utf-8")
            print(f"  sw.js CACHE_VERSION -> {stamp}")

    # Prune superseded content-hashed files. Every run emits a new hash, so
    # without this the directory accumulates stale copies of every logical file
    # — which bloats the deploy, lets the SW serve dead data, and slows the
    # catalog-performance parse test (it parses every collections-*.json it
    # finds; 8 stale copies took p75 from ~2ms to 81ms).
    keep = {build_info_path.name}
    for val in files.values():
        if isinstance(val, list):
            keep.update(val)
        else:
            keep.add(val)
    pruned = 0
    for path in output_dir.glob("*.json"):
        name = path.name
        if name in keep:
            continue
        # Only touch content-hashed artifacts we generate: <logical>.<12hex>.json
        if re.fullmatch(r".+\.[0-9a-f]{12}\.json", name):
            path.unlink()
            pruned += 1
    if pruned:
        print(f"  pruned {pruned} superseded hashed file(s)")
    print(f"  build-info.json  (snapshot_id={snapshot_id})"
          + (f"  (market_data_as_of={prior_market_data_as_of})" if prior_market_data_as_of else ""))

    total_size = sum(
        f.stat().st_size for f in output_dir.glob("*.json")
    )
    print(f"\nDone. {len(list(output_dir.glob('*.json')))} files, "
          f"{total_size // 1024}KB total in {output_dir}")


if __name__ == "__main__":
    main()
