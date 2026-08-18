#!/usr/bin/env python3
"""Fetch preview images and sample VRM URLs for all collections.

For each collection:
  1. Fetch collection image_url + banner_image_url from OpenSea API
  2. Fetch a sample NFT (token #1 or first available) to get its image_url + metadata
  3. If the collection has known VRM URLs, resolve them to HTTPS gateway URLs

Outputs:
  - os_scrape/preview_images.json (per-slug: collection image, sample NFT image, VRM URL)
  - Updates vrm_index.db with image_url, sample_nft_image, sample_nft_name columns
"""
import sqlite3, json, urllib.request, time, sys, re, concurrent.futures
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT  # repo root; scrape caches live under data/
DB = ROOT / "data" / "vrm_index.db"
API_KEY_PATH = Path.home() / ".opensea" / "api_key"
KEY = ""


def load_opensea_key() -> str:
    try:
        return API_KEY_PATH.read_text().strip()
    except FileNotFoundError as exc:
        raise SystemExit(f"No OpenSea API key at {API_KEY_PATH}") from exc

def os_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"X-API-KEY": KEY, "User-Agent": "vrm-scraper/6.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            if attempt < 2: time.sleep(2)
            else: return None

def ipfs_to_https(ipfs_url):
    """Convert ipfs:// URL to a public HTTPS gateway URL."""
    if not ipfs_url: return None
    if ipfs_url.startswith('ipfs://'):
        cid = ipfs_url[7:]
        # Cloudflare's public gateway shut down; use ipfs.io like the
        # reachability checker and the catalog viewer fallbacks.
        return f"https://ipfs.io/ipfs/{cid}"
    if ipfs_url.startswith('ar://'):
        cid = ipfs_url[5:]
        return f"https://arweave.net/{cid}"
    return ipfs_url if ipfs_url.startswith('http') else None

def main():
    global KEY
    KEY = load_opensea_key()
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # Get all slugs + their contracts from both collections and opensea_candidates
    collections = {}
    for r in conn.execute("SELECT id, name, opensea_slug, contract, chain FROM collections WHERE opensea_slug IS NOT NULL AND opensea_slug != '' AND opensea_slug != '—'"):
        collections[r['opensea_slug']] = {
            'id': r['id'], 'name': r['name'],
            'contract': r['contract'], 'chain': r['chain'],
        }
    # Also add collections WITHOUT slugs but WITH contracts
    for r in conn.execute("""
        SELECT id, name, contract, chain FROM collections
        WHERE (opensea_slug IS NULL OR opensea_slug = '' OR opensea_slug = '—')
        AND contract IS NOT NULL AND contract != '' AND contract != '—'
    """):
        key = f"contract:{r['contract'][:10]}"
        if key not in collections:
            collections[key] = {
                'id': r['id'], 'name': r['name'],
                'contract': r['contract'], 'chain': r['chain'],
                '_no_slug': True,
            }
    # Also add from opensea_candidates (these have slug + may have contract)
    for r in conn.execute("SELECT slug, name, contract, chain FROM opensea_candidates WHERE slug IS NOT NULL AND slug != ''"):
        if r['slug'] not in collections and ' ' not in r['slug']:
            collections[r['slug']] = {
                'id': r['slug'], 'name': r['name'] or r['slug'],
                'contract': r['contract'], 'chain': r['chain'] or 'ethereum',
            }

    # Also get VRM URLs from known_vrm_verified.json
    vrm_urls = {}
    kv_path = BASE / "data" / "os_scrape" / "known_vrm_verified.json"
    if kv_path.exists():
        for e in json.load(open(kv_path)):
            if e.get('vrm_url'):
                vrm_urls[e['slug']] = e['vrm_url']
    vcr_path = BASE / "data" / "os_scrape" / "vrm_check_results.json"
    if vcr_path.exists():
        d = json.load(open(vcr_path))
        for e in d.get('vrm', []):
            if e.get('vrm_url'):
                vrm_urls[e['slug']] = e['vrm_url']

    conn.close()

    slugs = sorted(collections.keys())
    # Filter out invalid slugs
    slugs = [s for s in slugs if ' ' not in s]
    print(f"Fetching preview images for {len(slugs)} collections...", file=sys.stderr)

    results = {}
    for i, slug in enumerate(slugs):
        c = collections[slug]
        entry = {
            'slug': slug,
            'name': c['name'],
            'collection_image': '',
            'banner_image': '',
            'sample_nft_name': '',
            'sample_nft_image': '',
            'vrm_url': vrm_urls.get(slug, ''),
            'vrm_url_https': '',
        }

        # 1. Collection image from OpenSea — by slug or resolve slug from contract
        no_slug = c.get('_no_slug', False)
        cd = None
        if not no_slug:
            cd = os_get(f"https://api.opensea.io/api/v2/collections/{slug}")
        else:
            # Resolve slug from contract via NFTs endpoint
            contract = c.get('contract')
            chain = c.get('chain', 'ethereum')
            os_chain = {'polygon':'matic','base':'base','optimism':'optimism','shape':'shape','arbitrum':'arbitrum','ape_chain':'apechain'}.get(chain, chain)
            nft_data = os_get(f"https://api.opensea.io/api/v2/chain/{os_chain}/contract/{contract}/nfts?limit=1")
            if nft_data and nft_data.get('nfts'):
                resolved_slug = nft_data['nfts'][0].get('collection', '')
                if resolved_slug:
                    entry['resolved_slug'] = resolved_slug
                    cd = os_get(f"https://api.opensea.io/api/v2/collections/{resolved_slug}")
        if cd:
            entry['collection_image'] = cd.get('image_url', '')
            entry['banner_image'] = cd.get('banner_image_url', '')
            entry['description'] = cd.get('description', '')
        time.sleep(0.15)

        # 2. Sample NFT image — fetch first NFT from the contract
        contract = c.get('contract')
        chain = c.get('chain', 'ethereum')
        if contract and contract != '—':
            # Map chain names to OpenSea API chain names
            os_chain = chain
            if chain == 'ethereum': os_chain = 'ethereum'
            elif chain == 'polygon': os_chain = 'matic'
            elif chain == 'base': os_chain = 'base'
            elif chain == 'optimism': os_chain = 'optimism'
            elif chain == 'shape': os_chain = 'shape'
            elif chain == 'multi': os_chain = 'ethereum'  # default to ethereum

            nft_data = os_get(f"https://api.opensea.io/api/v2/chain/{os_chain}/contract/{contract}/nfts?limit=1")
            if nft_data and nft_data.get('nfts'):
                nft = nft_data['nfts'][0]
                entry['sample_nft_name'] = nft.get('name', '')
                entry['sample_nft_image'] = nft.get('image_url', '') or nft.get('display_image_url', '')
            time.sleep(0.15)

        # 3. Convert VRM URL to HTTPS
        if entry['vrm_url']:
            entry['vrm_url_https'] = ipfs_to_https(entry['vrm_url']) or ''

        results[slug] = entry

        if (i+1) % 20 == 0:
            with_img = sum(1 for e in results.values() if e['collection_image'])
            with_nft = sum(1 for e in results.values() if e['sample_nft_image'])
            with_vrm = sum(1 for e in results.values() if e['vrm_url_https'])
            print(f"  [{i+1}/{len(slugs)}] images: {with_img}, nft imgs: {with_nft}, vrm urls: {with_vrm}", file=sys.stderr)

    # Save results
    json.dump(results, open(BASE / "data" / "os_scrape" / "preview_images.json", "w"), indent=2)

    # Update database
    conn = sqlite3.connect(str(DB))
    for col in ['collections', 'opensea_candidates']:
        for col_name in ['image_url', 'banner_image_url', 'sample_nft_image', 'sample_nft_name', 'vrm_url_https']:
            try: conn.execute(f"ALTER TABLE {col} ADD COLUMN {col_name} TEXT")
            except sqlite3.OperationalError: pass

    for slug, e in results.items():
        if slug.startswith('contract:'):
            # Update by contract instead of slug
            # Find the collection with this contract prefix
            contract_prefix = slug.split(':', 1)[1]
            # Save resolved slug if we found one
            resolved_slug = e.get('resolved_slug', '')
            if resolved_slug:
                conn.execute("""UPDATE collections SET
                    image_url=?, banner_image_url=?, sample_nft_image=?, sample_nft_name=?, vrm_url_https=?, opensea_slug=?
                    WHERE contract LIKE ?""",
                    (e['collection_image'], e['banner_image'], e['sample_nft_image'],
                     e['sample_nft_name'], e['vrm_url_https'], resolved_slug, f"{contract_prefix}%"))
            else:
                conn.execute("""UPDATE collections SET
                    image_url=?, banner_image_url=?, sample_nft_image=?, sample_nft_name=?, vrm_url_https=?
                    WHERE contract LIKE ?""",
                    (e['collection_image'], e['banner_image'], e['sample_nft_image'],
                     e['sample_nft_name'], e['vrm_url_https'], f"{contract_prefix}%"))
        else:
            conn.execute("""UPDATE collections SET
                image_url=?, banner_image_url=?, sample_nft_image=?, sample_nft_name=?, vrm_url_https=?
                WHERE opensea_slug=?""",
                (e['collection_image'], e['banner_image'], e['sample_nft_image'],
                 e['sample_nft_name'], e['vrm_url_https'], slug))
            conn.execute("""UPDATE opensea_candidates SET
                image_url=?, banner_image_url=?, sample_nft_image=?, sample_nft_name=?, vrm_url_https=?
                WHERE slug=?""",
                (e['collection_image'], e['banner_image'], e['sample_nft_image'],
                 e['sample_nft_name'], e['vrm_url_https'], slug))
    conn.commit()
    conn.close()

    # Summary
    with_img = sum(1 for e in results.values() if e['collection_image'])
    with_nft = sum(1 for e in results.values() if e['sample_nft_image'])
    with_vrm = sum(1 for e in results.values() if e['vrm_url_https'])
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Preview images saved to os_scrape/preview_images.json", file=sys.stderr)
    print(f"  Collection images: {with_img}/{len(results)}", file=sys.stderr)
    print(f"  Sample NFT images: {with_nft}/{len(results)}", file=sys.stderr)
    print(f"  VRM URLs (HTTPS):  {with_vrm}/{len(results)}", file=sys.stderr)
    print(f"  Database updated with image_url, banner_image_url, sample_nft_image, sample_nft_name, vrm_url_https", file=sys.stderr)

if __name__ == "__main__":
    main()
