#!/usr/bin/env python3
"""
Fetch comprehensive collection data from OpenSea API in a single sweep:
  - Collection metadata: description, category, safelist_status, owner,
    editors, fees (royalty), created_date, social links, NSFW flag,
    rarity strategy, total_supply, unique_item_count
  - Collection stats: num_owners (unique holders), floor_price, total
    volume/sales, 1d/7d/30d intervals

Uses slug when available, otherwise resolves slug from contract address.
Caches to data/os_scrape/collection_meta.json so re-runs are fast.
"""
import json, os, sqlite3, time, urllib.request, urllib.error
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"
CACHE_PATH = BASE / "data" / "os_scrape" / "collection_meta.json"
OSK = open(os.path.expanduser("~/.opensea/api_key")).read().strip()

CHAIN_MAP = {
    "polygon": "matic", "base": "base", "optimism": "optimism",
    "shape": "shape", "arbitrum": "arbitrum", "ape_chain": "apechain",
}

def os_get(url):
    req = urllib.request.Request(url, headers={
        "X-API-KEY": OSK, "User-Agent": "superyeti/1.0",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def resolve_slug_from_contract(contract, chain):
    """Resolve OpenSea slug by fetching an NFT from the contract."""
    os_chain = CHAIN_MAP.get(chain, chain)
    try:
        data = os_get(
            f"https://api.opensea.io/api/v2/chain/{os_chain}"
            f"/contract/{contract}/nfts?limit=1"
        )
        if data.get("nfts"):
            return data["nfts"][0].get("collection", "")
    except Exception:
        pass
    return ""

def fetch_collection(slug):
    """Fetch collection metadata from OpenSea v2 API."""
    return os_get(f"https://api.opensea.io/api/v2/collections/{slug}")

def fetch_stats(slug):
    """Fetch collection stats from OpenSea v2 API."""
    try:
        return os_get(f"https://api.opensea.io/api/v2/collections/{slug}/stats")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise

def extract_fields(meta, stats):
    """Extract the fields we want from the API responses."""
    fees = meta.get("fees", [])
    primary_fee = fees[0] if fees else {}
    secondary_fee = fees[1] if len(fees) > 1 else {}

    total_stats = stats.get("total", {}) if stats else {}
    intervals = stats.get("intervals", []) if stats else {}
    interval_map = {i["interval"]: i for i in intervals} if intervals else {}

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
        "num_owners": total_stats.get("num_owners", 0),
        "floor_price": total_stats.get("floor_price", 0),
        "floor_price_symbol": total_stats.get("floor_price_symbol", ""),
        "total_volume": total_stats.get("volume", 0),
        "total_sales": total_stats.get("sales", 0),
        "one_day_volume": (interval_map.get("one_day") or {}).get("volume", 0),
        "one_day_sales": (interval_map.get("one_day") or {}).get("sales", 0),
        "seven_day_volume": (interval_map.get("seven_day") or {}).get("volume", 0),
        "seven_day_sales": (interval_map.get("seven_day") or {}).get("sales", 0),
        "thirty_day_volume": (interval_map.get("thirty_day") or {}).get("volume", 0),
        "thirty_day_sales": (interval_map.get("thirty_day") or {}).get("sales", 0),
    }

NEW_COLUMNS = [
    ("num_owners", "INTEGER"),
    ("floor_price", "REAL"),
    ("floor_price_symbol", "TEXT"),
    ("total_volume", "REAL"),
    ("total_sales", "INTEGER"),
    ("category", "TEXT"),
    ("safelist_status", "TEXT"),
    ("owner_address", "TEXT"),
    ("royalty_fee", "REAL"),
    ("royalty_recipient", "TEXT"),
    ("instagram_username", "TEXT"),
    ("telegram_url", "TEXT"),
    ("is_nsfw", "INTEGER"),
    ("rarity_strategy", "TEXT"),
    ("unique_item_count", "INTEGER"),
    ("one_day_volume", "REAL"),
    ("one_day_sales", "INTEGER"),
    ("seven_day_volume", "REAL"),
    ("seven_day_sales", "INTEGER"),
    ("thirty_day_volume", "REAL"),
    ("thirty_day_sales", "INTEGER"),
]

def main():
    # Load cache
    cache = {}
    if CACHE_PATH.exists():
        cache = json.load(open(CACHE_PATH))

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Add missing columns
    existing_cols = {c[1] for c in conn.execute("PRAGMA table_info(collections)").fetchall()}
    for col_name, col_type in NEW_COLUMNS:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE collections ADD COLUMN {col_name} {col_type}")
            print(f"  + column {col_name} ({col_type})")

    # Get all collections with slug or contract
    rows = conn.execute("""
        SELECT id, name, opensea_slug, contract, chain
        FROM collections
        ORDER BY name
    """).fetchall()

    fetched = 0
    skipped = 0
    for row in rows:
        slug = row["opensea_slug"] or ""
        contract = row["contract"] or ""
        chain = row["chain"] or "ethereum"

        # Skip slug resolution for shared store contracts (multiple collections share one contract)
        SHARED_STORE = "0x495f947276749ce646f68ac8c248420045cb7b5e"
        is_shared_store = contract and contract.lower().startswith(SHARED_STORE)

        # Resolve slug if missing
        if (not slug or slug == "—" or " " in slug) and contract and len(contract) >= 20 and not is_shared_store:
            cache_key = f"contract:{contract[:10]}"
            if cache_key in cache and cache[cache_key].get("resolved_slug"):
                slug = cache[cache_key]["resolved_slug"]
            else:
                slug = resolve_slug_from_contract(contract, chain)
                if slug:
                    print(f"  → {row['name']}: resolved slug = {slug}")
                    time.sleep(0.3)

        if not slug or " " in slug:
            # Try contract resolution (skip shared store contracts)
            if contract and len(contract) >= 20 and not is_shared_store:
                cache_key = f"contract:{contract[:10]}"
                cached = cache.get(cache_key)
                if cached and cached.get("resolved_slug"):
                    slug = cached["resolved_slug"]
                else:
                    slug = resolve_slug_from_contract(contract, chain)
                    if slug:
                        print(f"  → {row['name']}: resolved slug = {slug}")
                        time.sleep(0.3)
            if not slug:
                skipped += 1
                continue

        # Check cache (refresh if > 24h old)
        cache_key = slug
        cached = cache.get(cache_key)
        use_cache = cached and (time.time() - cached.get("_ts", 0) < 86400)

        if use_cache:
            fields = cached["fields"]
        else:
            try:
                meta = fetch_collection(slug)
                time.sleep(0.2)
                stats = fetch_stats(slug)
                time.sleep(0.2)
                fields = extract_fields(meta, stats)
                fields["_ts"] = time.time()
                cache[cache_key] = {"fields": fields, "resolved_slug": slug}
                fetched += 1
            except urllib.error.HTTPError as e:
                if e.code in (401, 404):
                    # Slug is wrong — try contract resolution as fallback
                    if contract and len(contract) >= 20:
                        new_slug = resolve_slug_from_contract(contract, chain)
                        if new_slug and new_slug != slug:
                            time.sleep(0.3)
                            try:
                                meta = fetch_collection(new_slug)
                                time.sleep(0.2)
                                stats = fetch_stats(new_slug)
                                time.sleep(0.2)
                                fields = extract_fields(meta, stats)
                                fields["_ts"] = time.time()
                                cache[cache_key] = {"fields": fields, "resolved_slug": new_slug}
                                # Update slug in DB
                                conn.execute("UPDATE collections SET opensea_slug=? WHERE id=?", (new_slug, row["id"]))
                                print(f"  ↻ {row['name']}: slug '{slug}' → '{new_slug}'")
                                slug = new_slug
                                fetched += 1
                                continue
                            except Exception:
                                pass
                    print(f"  ✗ {row['name']}: slug '{slug}' not found ({e.code})")
                    cache[cache_key] = {"fields": {}, "resolved_slug": slug, "_ts": time.time()}
                else:
                    print(f"  ✗ {row['name']}: HTTP {e.code}")
                continue
            except Exception as e:
                print(f"  ✗ {row['name']}: {str(e)[:60]}")
                continue

        # Update DB — only set fields that have values
        # For existing fields like description/release_date, only fill if empty
        # For new fields (num_owners, floor_price, etc.), always update (they change over time)
        fill_only = {"name", "description", "release_date", "image_url", "banner_image_url",
                     "project_url", "discord_url", "twitter_username", "total_supply"}
        updates = []
        params = []
        for key, val in fields.items():
            if key.startswith("_"):
                continue
            if val is None or val == "" or val == 0:
                continue
            if key in fill_only:
                # Only fill if DB value is empty
                current = conn.execute(
                    f"SELECT {key} FROM collections WHERE id=?", (row["id"],)
                ).fetchone()
                if current and current[0]:
                    continue
            updates.append(f"{key}=?")
            params.append(val)

        if updates:
            # Also save resolved slug
            if slug and (not row["opensea_slug"] or row["opensea_slug"] != slug):
                updates.append("opensea_slug=?")
                params.append(slug)

            params.append(row["id"])
            conn.execute(
                f"UPDATE collections SET {', '.join(updates)} WHERE id=?",
                params,
            )

        # Save cache periodically
        if fetched % 10 == 0:
            json.dump(cache, open(CACHE_PATH, "w"), indent=2)

    # Save cache
    json.dump(cache, open(CACHE_PATH, "w"), indent=2)
    conn.commit()
    conn.close()

    print(f"\nFetched: {fetched}, Skipped (no slug): {skipped}")
    print(f"Cache: {len(cache)} entries in {CACHE_PATH}")

if __name__ == "__main__":
    main()
