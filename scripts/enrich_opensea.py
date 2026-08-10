#!/usr/bin/env python3
"""Enrich the collections table with OpenSea API v2 metadata and market stats.

This script replaces the per-collection HTTP loop in fetch_collection_meta.py
with a cache-aware, batched enrichment flow built on the centralized
OpenSeaClient.  It reads TTL policy from config/cache_policy.yaml, persists raw
API responses in the source_cache SQLite table (migration 008), and writes the
extracted fields back into the collections table.

Usage:
    python scripts/enrich_opensea.py                 # full refresh (cache-aware)
    python scripts/enrich_opensea.py --stats-only    # floor/volume only
    python scripts/enrich_opensea.py --meta-only     # metadata only
    python scripts/enrich_opensea.py --slug pixelbeasts
    python scripts/enrich_opensea.py --force         # ignore cache, re-fetch all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

# Make sibling modules importable whether run as a script or a package.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))

from scripts.opensea_client import OpenSeaClient  # noqa: E402
from scripts.resolve_opensea_collections import resolve  # noqa: E402

_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_DB = _REPO_ROOT / "data" / "vrm_index.db"
_CACHE_POLICY_PATH = _REPO_ROOT / "config" / "cache_policy.yaml"
_BUILD_INFO_PATH = _REPO_ROOT / "static" / "data" / "build-info.json"

SHARED_STOREFRONT_CONTRACTS: set[str] = {
    "0x495f947276749ce646f68ac8c248420045cb7b5e",
}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


# --------------------------------------------------------------------------- policy


def load_cache_policy(path: Path = _CACHE_POLICY_PATH) -> dict[str, Any]:
    """Load config/cache_policy.yaml and return the parsed dict."""
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _ttl(policy: dict[str, Any], *keys: str, default: int = 86400) -> int:
    """Walk into the policy dict following *keys* and return an int TTL."""
    node: Any = policy
    for k in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(k)
    if isinstance(node, bool):
        return default
    if isinstance(node, int):
        return node
    return default


# --------------------------------------------------------------------------- cache


class Cache:
    """Thin wrapper around the source_cache SQLite table (migration 008)."""

    def __init__(self, db_path: str | Path = _DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # Ensure the table exists even if migration 008 hasn't been applied.
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_cache (
                    key            TEXT     NOT NULL PRIMARY KEY,
                    endpoint       TEXT     NOT NULL,
                    fetched_at     TEXT     NOT NULL,
                    expires_at     TEXT     NOT NULL,
                    etag           TEXT,
                    last_modified  TEXT,
                    status         INTEGER,
                    response_json  TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_sc_expires
                    ON source_cache(expires_at);
                CREATE INDEX IF NOT EXISTS idx_sc_endpoint
                    ON source_cache(endpoint);
                """
            )
            self._conn.commit()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Cache":
        _ = self.conn  # force open
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    async def __aenter__(self) -> "Cache":
        return self.__enter__()

    async def __aexit__(self, *exc: Any) -> None:
        self.__exit__(*exc)

    # ----------------------------------------------------------------- read

    def get_cached(self, key: str) -> tuple[Optional[dict[str, Any]], bool]:
        """Return (response_json, is_fresh) for *key*.

        ``is_fresh`` is True only when the row exists and expires_at is in the
        future.  A stale row still returns its parsed response_json so callers
        can use it as a fallback, but with is_fresh=False.
        """
        row = self.conn.execute(
            "SELECT response_json, expires_at, status FROM source_cache WHERE key=?",
            (key,),
        ).fetchone()
        if row is None:
            return None, False
        raw = row["response_json"]
        if not raw:
            return None, False
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None, False
        is_fresh = False
        try:
            expires_at = datetime.fromisoformat(row["expires_at"])
            is_fresh = expires_at > datetime.now(timezone.utc)
        except (ValueError, TypeError):
            is_fresh = False
        return data, is_fresh

    def is_expired(self, key: str) -> bool:
        """True if the cached row is missing or past its expires_at."""
        _, fresh = self.get_cached(key)
        return not fresh

    # ---------------------------------------------------------------- write

    def set_cached(
        self,
        key: str,
        endpoint: str,
        response_json: Any,
        ttl_seconds: int,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        status: int = 200,
    ) -> None:
        """Insert or replace a cache row."""
        now = datetime.now(timezone.utc)
        if ttl_seconds < 0:
            # -1 means "never expires" — push far into the future.
            expires = datetime.max.replace(tzinfo=timezone.utc)
        else:
            from datetime import timedelta

            expires = now + timedelta(seconds=ttl_seconds)
        body = json.dumps(response_json) if response_json is not None else None
        self.conn.execute(
            """
            INSERT INTO source_cache
                (key, endpoint, fetched_at, expires_at, etag, last_modified, status, response_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                endpoint       = excluded.endpoint,
                fetched_at     = excluded.fetched_at,
                expires_at     = excluded.expires_at,
                etag           = excluded.etag,
                last_modified  = excluded.last_modified,
                status         = excluded.status,
                response_json  = excluded.response_json
            """,
            (
                key,
                endpoint,
                now.isoformat(),
                expires.isoformat(),
                etag,
                last_modified,
                status,
                body,
            ),
        )
        self.conn.commit()


# --------------------------------------------------------------------------- field extraction


def extract_meta_fields(meta: dict[str, Any]) -> dict[str, Any]:
    """Map a GET /collections/{slug} response to collections-table columns."""
    fees = meta.get("fees", []) or []
    primary_fee = fees[0] if fees else {}
    return {
        "name": meta.get("name", ""),
        "description": meta.get("description", ""),
        "category": meta.get("category", ""),
        "safelist_status": meta.get("safelist_status", ""),
        "owner_address": meta.get("owner", ""),
        "royalty_fee": primary_fee.get("fee", 0),
        "royalty_recipient": primary_fee.get("recipient", ""),
        "release_date": meta.get("created_date", ""),
        "instagram_username": meta.get("instagram_username", ""),
        "telegram_url": meta.get("telegram_url", ""),
        "is_nsfw": 1 if meta.get("is_nsfw") else 0,
        "rarity_strategy": (meta.get("rarity") or {}).get("strategy_id", ""),
        "total_supply": meta.get("total_supply", 0),
        "unique_item_count": meta.get("unique_item_count", 0),
        "image_url": meta.get("image_url", ""),
        "banner_image_url": meta.get("banner_image_url", ""),
        "project_url": meta.get("project_url", "") or meta.get("external_url", ""),
        "discord_url": meta.get("discord_url", ""),
        "twitter_username": meta.get("twitter_username", ""),
    }


def extract_stats_fields(stats: dict[str, Any]) -> dict[str, Any]:
    """Map a GET /collections/{slug}/stats response to collections-table columns."""
    total = stats.get("total", {}) if stats else {}
    intervals = stats.get("intervals", []) if stats else []
    interval_map = {i["interval"]: i for i in intervals} if intervals else {}
    return {
        "num_owners": total.get("num_owners", 0),
        "floor_price": total.get("floor_price", 0),
        "floor_price_symbol": total.get("floor_price_symbol", ""),
        "total_volume": total.get("volume", 0),
        "total_sales": total.get("sales", 0),
        "one_day_volume": (interval_map.get("one_day") or {}).get("volume", 0),
        "one_day_sales": (interval_map.get("one_day") or {}).get("sales", 0),
        "seven_day_volume": (interval_map.get("seven_day") or {}).get("volume", 0),
        "seven_day_sales": (interval_map.get("seven_day") or {}).get("sales", 0),
        "thirty_day_volume": (interval_map.get("thirty_day") or {}).get("volume", 0),
        "thirty_day_sales": (interval_map.get("thirty_day") or {}).get("sales", 0),
    }


# --------------------------------------------------------------------------- DB writes


def _update_collection(
    conn: sqlite3.Connection, collection_id: str, fields: dict[str, Any]
) -> None:
    """UPDATE collections SET ... WHERE id = ? for the given fields."""
    if not fields:
        return
    # Only keep columns that actually exist on the collections table.
    existing = {
        r[1]
        for r in conn.execute("PRAGMA table_info(collections)").fetchall()
    }
    clean = {k: v for k, v in fields.items() if k in existing}
    if not clean:
        return
    set_clause = ", ".join(f"{k}=?" for k in clean)
    conn.execute(
        f"UPDATE collections SET {set_clause} WHERE id=?",
        (*clean.values(), collection_id),
    )
    conn.commit()


# --------------------------------------------------------------------------- enrichment


async def enrich_collection(
    client: OpenSeaClient,
    cache: Cache,
    collection_id: str,
    slug: str,
    chain: str = "ethereum",
    contract: str = "",
    *,
    ttl_meta: int = 2592000,
    force: bool = False,
) -> dict[str, Any]:
    """Fetch (or read from cache) collection metadata for *slug* and update the DB."""
    key = f"opensea:collection:{slug}:meta"
    data, fresh = cache.get_cached(key)
    if fresh and not force:
        _log(f"[enrich] meta cache hit: {slug}")
    else:
        _log(f"[enrich] fetching meta: {slug}")
        data = await client.get_collection(slug)
        cache.set_cached(key, "collection_meta", data, ttl_meta, status=200)
    if not isinstance(data, dict):
        return {}
    fields = extract_meta_fields(data)
    _update_collection(cache.conn, collection_id, fields)
    return fields


async def enrich_stats(
    client: OpenSeaClient,
    cache: Cache,
    slug: str,
    collection_id: Optional[str] = None,
    *,
    ttl_stats: int = 21600,
    force: bool = False,
) -> dict[str, Any]:
    """Fetch (or read from cache) collection stats for *slug* and update the DB."""
    key = f"opensea:stats:{slug}"
    data, fresh = cache.get_cached(key)
    if fresh and not force:
        _log(f"[enrich] stats cache hit: {slug}")
    else:
        _log(f"[enrich] fetching stats: {slug}")
        data = await client.get_collection_stats(slug)
        cache.set_cached(key, "collection_stats", data, ttl_stats, status=200)
    if not isinstance(data, dict):
        return {}
    fields = extract_stats_fields(data)
    if collection_id:
        _update_collection(cache.conn, collection_id, fields)
    return fields


async def batch_enrich_meta(
    client: OpenSeaClient,
    cache: Cache,
    slugs: list[str],
    *,
    id_by_slug: Optional[dict[str, str]] = None,
    ttl_meta: int = 2592000,
    force: bool = False,
) -> dict[str, dict[str, Any]]:
    """Batch-refresh metadata for many slugs in a single API call.

    Only slugs whose cache is missing or stale are sent to the batch endpoint;
    the rest are served from cache.  Returns {slug: updated_fields}.
    """
    id_by_slug = id_by_slug or {}
    results: dict[str, dict[str, Any]] = {}

    # Partition into fresh-cached vs needs-refresh.
    needs_refresh: list[str] = []
    for slug in slugs:
        key = f"opensea:collection:{slug}:meta"
        data, fresh = cache.get_cached(key)
        if fresh and not force:
            if isinstance(data, dict):
                fields = extract_meta_fields(data)
                results[slug] = fields
                cid = id_by_slug.get(slug)
                if cid:
                    _update_collection(cache.conn, cid, fields)
            continue
        needs_refresh.append(slug)

    if not needs_refresh:
        _log(f"[enrich] batch meta: all {len(slugs)} slugs fresh from cache")
        return results

    _log(f"[enrich] batch meta: requesting {len(needs_refresh)} slugs in one call")
    batch_resp = await client.batch_collections(needs_refresh)

    # OpenSea returns {"collections": [ {slug: ..., ...}, ... ]}.
    collections = (
        batch_resp.get("collections")
        if isinstance(batch_resp, dict)
        else None
    )
    if not isinstance(collections, list):
        collections = []

    by_slug: dict[str, dict[str, Any]] = {}
    for item in collections:
        if isinstance(item, dict) and item.get("slug"):
            by_slug[item["slug"]] = item

    for slug in needs_refresh:
        meta = by_slug.get(slug)
        key = f"opensea:collection:{slug}:meta"
        if meta is None:
            # OpenSea didn't return this slug — cache a negative result.
            cache.set_cached(
                key, "collection_meta", None, ttl_meta, status=404
            )
            continue
        cache.set_cached(key, "collection_meta", meta, ttl_meta, status=200)
        fields = extract_meta_fields(meta)
        results[slug] = fields
        cid = id_by_slug.get(slug)
        if cid:
            _update_collection(cache.conn, cid, fields)

    return results


# --------------------------------------------------------------------------- full sweep


def _load_collection_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all collections that have (or could resolve) an opensea_slug."""
    return conn.execute(
        "SELECT id, name, chain, contract, opensea_slug FROM collections ORDER BY name"
    ).fetchall()


def _is_shared_storefront(contract: str) -> bool:
    return bool(contract) and contract.lower() in SHARED_STOREFRONT_CONTRACTS


async def _resolve_missing_slugs(
    client: OpenSeaClient,
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    db_path: Path,
) -> dict[str, str]:
    """Resolve slugs for shared-storefront collections missing one.

    Returns a mapping of collection_id -> resolved slug.  Also persists the
    resolved slug back to the collections table.
    """
    resolved: dict[str, str] = {}
    for row in rows:
        slug = (row["opensea_slug"] or "").strip()
        contract = row["contract"] or ""
        chain = row["chain"] or "ethereum"
        if slug and " " not in slug and slug != "—":
            continue
        if not contract or len(contract) < 20:
            continue
        if not _is_shared_storefront(contract):
            # Non-shared contracts: try a lightweight contract-NFT lookup.
            pass
        _log(f"[enrich] resolving slug for {row['name']} ({contract[:10]}…)")
        try:
            result = await resolve(
                client,
                chain,
                contract,
                db_path=str(db_path),
                allow_sweep=False,
            )
        except Exception as e:  # noqa: BLE001
            _log(f"[enrich] resolve failed for {row['name']}: {e}")
            continue
        new_slug = result.get("opensea_slug")
        if new_slug:
            resolved[row["id"]] = new_slug
            conn.execute(
                "UPDATE collections SET opensea_slug=? WHERE id=?",
                (new_slug, row["id"]),
            )
            conn.commit()
            _log(f"[enrich]   → {row['name']}: slug = {new_slug}")
    return resolved


def _write_build_info(market_data_as_of: Optional[str] = None) -> None:
    """Emit static/data/build-info.json with generation + market-data timestamps."""
    now = _now_iso()
    payload = {
        "generated_at": now,
        "market_data_as_of": market_data_as_of or now,
        "schema_version": "1.0",
    }
    _BUILD_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_BUILD_INFO_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    _log(f"[enrich] wrote {_BUILD_INFO_PATH}")


async def enrich_all(
    client: OpenSeaClient,
    cache: Cache,
    db_path: str | Path = _DEFAULT_DB,
    *,
    stats_only: bool = False,
    meta_only: bool = False,
    force: bool = False,
) -> None:
    """Full enrichment sweep: resolve slugs, batch meta, per-slug stats."""
    db_path = Path(db_path)
    policy = load_cache_policy()
    ttl_meta = _ttl(policy, "opensea", "collection_meta", default=2592000)
    ttl_stats = _ttl(policy, "opensea", "floor_price_static", default=21600)

    conn = cache.conn
    rows = _load_collection_rows(conn)

    # 1. Resolve missing slugs (shared-storefront collections).
    if not stats_only:
        resolved = await _resolve_missing_slugs(client, conn, rows, db_path)
        if resolved:
            rows = _load_collection_rows(conn)

    # Build slug -> collection_id map for rows that have a usable slug.
    id_by_slug: dict[str, str] = {}
    slugs: list[str] = []
    for row in rows:
        slug = (row["opensea_slug"] or "").strip()
        if not slug or " " in slug or slug == "—":
            continue
        id_by_slug[slug] = row["id"]
        slugs.append(slug)

    _log(f"[enrich] {len(slugs)} collections with slugs")

    # 2. Per-slug metadata refresh. POST /collections/batch is gated to paid API
    #    tiers (it 401s "API key has expired" on the standard key), so refresh
    #    each collection via GET /collections/{slug}, which works fine.
    if not stats_only and slugs:
        for slug in slugs:
            try:
                await enrich_collection(
                    client,
                    cache,
                    id_by_slug.get(slug, ""),
                    slug,
                    ttl_meta=ttl_meta,
                    force=force,
                )
            except Exception as e:  # noqa: BLE001
                _log(f"[enrich] meta failed for {slug}: {e}")

    # 3. Per-slug stats refresh (cannot be batched by OpenSea).
    latest_market_ts: Optional[str] = None
    if not meta_only and slugs:
        for slug in slugs:
            try:
                await enrich_stats(
                    client,
                    cache,
                    slug,
                    collection_id=id_by_slug.get(slug),
                    ttl_stats=ttl_stats,
                    force=force,
                )
                latest_market_ts = _now_iso()
            except Exception as e:  # noqa: BLE001
                _log(f"[enrich] stats failed for {slug}: {e}")

    # 4. Emit build-info.json.
    _write_build_info(market_data_as_of=latest_market_ts)


# --------------------------------------------------------------------------- CLI


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Enrich collections with OpenSea API v2 metadata and stats."
    )
    p.add_argument(
        "--db",
        default=str(_DEFAULT_DB),
        help="Path to the SQLite DB (default: data/vrm_index.db)",
    )
    p.add_argument(
        "--stats-only",
        action="store_true",
        help="Skip metadata; only refresh market stats.",
    )
    p.add_argument(
        "--meta-only",
        action="store_true",
        help="Skip stats; only refresh collection metadata.",
    )
    p.add_argument(
        "--slug",
        default=None,
        help="Enrich a single collection by OpenSea slug.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Ignore cache and re-fetch everything.",
    )
    return p


async def _async_main(args: argparse.Namespace) -> None:
    policy = load_cache_policy()
    ttl_meta = _ttl(policy, "opensea", "collection_meta", default=2592000)
    ttl_stats = _ttl(policy, "opensea", "floor_price_static", default=21600)

    async with OpenSeaClient() as client, Cache(args.db) as cache:
        if args.slug:
            # Single-slug mode — look up the collection_id if present.
            row = cache.conn.execute(
                "SELECT id FROM collections WHERE opensea_slug=? LIMIT 1",
                (args.slug,),
            ).fetchone()
            collection_id = row["id"] if row else ""
            if not args.stats_only:
                await enrich_collection(
                    client,
                    cache,
                    collection_id,
                    args.slug,
                    ttl_meta=ttl_meta,
                    force=args.force,
                )
            if not args.meta_only:
                await enrich_stats(
                    client,
                    cache,
                    args.slug,
                    collection_id=collection_id or None,
                    ttl_stats=ttl_stats,
                    force=args.force,
                )
            _write_build_info(market_data_as_of=_now_iso())
            return

        await enrich_all(
            client,
            cache,
            db_path=args.db,
            stats_only=args.stats_only,
            meta_only=args.meta_only,
            force=args.force,
        )


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
