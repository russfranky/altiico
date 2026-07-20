#!/usr/bin/env python3
"""Fetch Discord (and other social) links from OpenSea API for all collections.

Checks if Discord invite links are still valid (not expired/revoked).
Discord invite API: https://discord.com/api/v9/invites/{code} returns
200+json for valid, 404 for invalid/expired.

Outputs:
  - os_scrape/social_links.json (per-slug: discord_url, twitter, instagram, etc.)
  - os_scrape/discord_status.json (per-slug: discord invite code, status, member count)
  - Updates vrm_index.db with discord_url, discord_status columns
"""
import sqlite3, json, urllib.request, urllib.error, time, sys, re, concurrent.futures
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"
KEY = open(__import__('os').path.expanduser('~/.opensea/api_key')).read().strip()

def os_get(url):
    req = urllib.request.Request(url, headers={"X-API-KEY": KEY, "User-Agent": "vrm-scraper/5.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.load(r)
        except Exception as e:
            if attempt < 2: time.sleep(2)
            else: return None

def check_discord(discord_url):
    """Check if a Discord invite link is still valid."""
    if not discord_url:
        return {'status': 'none', 'code': None}
    # Extract invite code from various URL formats
    m = re.search(r'discord\.(?:gg|com/invite)/([a-zA-Z0-9]+)', discord_url)
    if not m:
        return {'status': 'unknown', 'code': None, 'url': discord_url}
    code = m.group(1)
    # Use Discord's public invite API
    api_url = f"https://discord.com/api/v9/invites/{code}?with_counts=true&with_expiration=true"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
            return {
                'status': 'alive',
                'code': code,
                'guild_name': d.get('guild', {}).get('name', ''),
                'member_count': d.get('approximate_member_count', 0),
                'presence_count': d.get('approximate_presence_count', 0),
                'expires_at': d.get('expires_at'),
                'url': discord_url,
            }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {'status': 'dead', 'code': code, 'url': discord_url}
        elif e.code == 429:
            return {'status': 'rate_limited', 'code': code, 'url': discord_url}
        return {'status': 'error', 'code': code, 'http_code': e.code, 'url': discord_url}
    except Exception as e:
        return {'status': 'error', 'code': code, 'error': str(e), 'url': discord_url}

def main():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    slugs = [r[0] for r in conn.execute(
        "SELECT DISTINCT slug FROM opensea_candidates WHERE slug IS NOT NULL AND slug != '' "
        "UNION SELECT DISTINCT opensea_slug FROM collections WHERE opensea_slug IS NOT NULL AND opensea_slug != '' AND opensea_slug != '—'"
    )]
    # Also get collections without slugs but with contracts
    contract_entries = []
    for r in conn.execute("""
        SELECT name, contract, chain FROM collections
        WHERE (opensea_slug IS NULL OR opensea_slug = '' OR opensea_slug = '—')
        AND contract IS NOT NULL AND contract != '' AND contract != '—'
    """):
        contract_entries.append(dict(r))
    conn.close()
    slugs = sorted(set(s for s in slugs if ' ' not in s))  # skip invalid slugs
    print(f"Fetching social links for {len(slugs)} slug-based + {len(contract_entries)} contract-based collections...", file=sys.stderr)

    # Phase 1: Fetch all social links from OpenSea
    social = {}
    for i, slug in enumerate(slugs):
        d = os_get(f"https://api.opensea.io/api/v2/collections/{slug}")
        if d:
            social[slug] = {
                'name': d.get('name', ''),
                'discord_url': d.get('discord_url', ''),
                'twitter_username': d.get('twitter_username', ''),
                'instagram_username': d.get('instagram_username', ''),
                'telegram_url': d.get('telegram_url', ''),
                'project_url': d.get('project_url', ''),
                'wiki_url': d.get('wiki_url', ''),
            }
        if (i+1) % 30 == 0:
            print(f"  [{i+1}/{len(slugs)}] {len(social)} fetched", file=sys.stderr)
        time.sleep(0.15)

    json.dump(social, open(BASE / "os_scrape" / "social_links.json", "w"), indent=2)
    print(f"\nFetched social links for {len(social)} slug-based collections", file=sys.stderr)

    # Phase 1b: Fetch social links for contract-based collections (no slug)
    CHAIN_MAP = {'ethereum':'ethereum','polygon':'matic','base':'base','optimism':'optimism','shape':'shape','arbitrum':'arbitrum','ape_chain':'apechain'}
    contract_social = {}
    for i, c in enumerate(contract_entries):
        contract = c['contract']
        chain = CHAIN_MAP.get(c.get('chain','ethereum'), 'ethereum')
        # Resolve slug from contract via NFTs endpoint
        nft_data = os_get(f"https://api.opensea.io/api/v2/chain/{chain}/contract/{contract}/nfts?limit=1")
        resolved_slug = None
        if nft_data and nft_data.get('nfts'):
            resolved_slug = nft_data['nfts'][0].get('collection', '')
        if resolved_slug:
            d = os_get(f"https://api.opensea.io/api/v2/collections/{resolved_slug}")
            if d:
                key = f"contract:{contract[:10]}"
                contract_social[key] = {
                    'name': d.get('name', ''),
                    'discord_url': d.get('discord_url', ''),
                    'twitter_username': d.get('twitter_username', ''),
                    'instagram_username': d.get('instagram_username', ''),
                    'telegram_url': d.get('telegram_url', ''),
                    'project_url': d.get('project_url', ''),
                    'contract': contract,
                }
        if (i+1) % 20 == 0:
            print(f"  [contract {i+1}/{len(contract_entries)}] {len(contract_social)} fetched", file=sys.stderr)
        time.sleep(0.15)

    # Merge contract-based into social
    social.update(contract_social)
    print(f"Total social links: {len(social)} (incl. {len(contract_social)} contract-based)", file=sys.stderr)

    # Phase 2: Check Discord invite links
    discord_urls = {slug: s['discord_url'] for slug, s in social.items() if s.get('discord_url')}
    print(f"Checking {len(discord_urls)} Discord invite links...", file=sys.stderr)

    discord_status = {}
    def check_one(slug_url):
        slug, url = slug_url
        return slug, check_discord(url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(check_one, (s, u)): s for s, u in discord_urls.items()}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            slug, result = fut.result()
            discord_status[slug] = result
            done += 1
            icon = {'alive': '✓', 'dead': '✗', 'rate_limited': '⏳', 'error': '?', 'none': '—'}.get(result['status'], '?')
            if result['status'] == 'alive':
                print(f"  [{done}/{len(discord_urls)}] {icon} {slug} → {result.get('guild_name','?')} ({result.get('member_count',0):,} members)", file=sys.stderr)
            elif result['status'] != 'alive':
                print(f"  [{done}/{len(discord_urls)}] {icon} {slug} → {result['status']}", file=sys.stderr)
            time.sleep(0.5)  # be gentle with Discord API

    json.dump(discord_status, open(BASE / "os_scrape" / "discord_status.json", "w"), indent=2)

    # Phase 3: Update database
    conn = sqlite3.connect(str(DB))
    for col in ['collections', 'opensea_candidates']:
        try: conn.execute(f"ALTER TABLE {col} ADD COLUMN discord_url TEXT")
        except sqlite3.OperationalError: pass
        try: conn.execute(f"ALTER TABLE {col} ADD COLUMN discord_status TEXT")
        except sqlite3.OperationalError: pass
        try: conn.execute(f"ALTER TABLE {col} ADD COLUMN discord_members INTEGER")
        except sqlite3.OperationalError: pass
        try: conn.execute(f"ALTER TABLE {col} ADD COLUMN twitter_username TEXT")
        except sqlite3.OperationalError: pass

    for slug, s in social.items():
        ds = discord_status.get(slug, {})
        if slug.startswith('contract:'):
            contract_prefix = slug.split(':', 1)[1]
            conn.execute("UPDATE collections SET discord_url=?, discord_status=?, discord_members=?, twitter_username=? WHERE contract LIKE ?",
                          (s.get('discord_url',''), ds.get('status',''), ds.get('member_count',0), s.get('twitter_username',''), f"{contract_prefix}%"))
        else:
            conn.execute("UPDATE opensea_candidates SET discord_url=?, discord_status=?, discord_members=?, twitter_username=? WHERE slug=?",
                          (s.get('discord_url',''), ds.get('status',''), ds.get('member_count',0), s.get('twitter_username',''), slug))
            conn.execute("UPDATE collections SET discord_url=?, discord_status=?, discord_members=?, twitter_username=? WHERE opensea_slug=?",
                          (s.get('discord_url',''), ds.get('status',''), ds.get('member_count',0), s.get('twitter_username',''), slug))
    conn.commit()
    conn.close()

    # Summary
    alive = sum(1 for d in discord_status.values() if d['status'] == 'alive')
    dead = sum(1 for d in discord_status.values() if d['status'] == 'dead')
    none_count = sum(1 for s in social.values() if not s.get('discord_url'))
    total_members = sum(d.get('member_count', 0) for d in discord_status.values() if d['status'] == 'alive')

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Discord link results:", file=sys.stderr)
    print(f"  ✓ Alive:       {alive} (total {total_members:,} members)", file=sys.stderr)
    print(f"  ✗ Dead:        {dead}", file=sys.stderr)
    print(f"  — No Discord:  {none_count}", file=sys.stderr)
    print(f"  Twitter:       {sum(1 for s in social.values() if s.get('twitter_username'))}", file=sys.stderr)
    print(f"  Instagram:     {sum(1 for s in social.values() if s.get('instagram_username'))}", file=sys.stderr)
    print(f"  Project URL:   {sum(1 for s in social.values() if s.get('project_url'))}", file=sys.stderr)
    print(f"\nFiles: os_scrape/social_links.json, os_scrape/discord_status.json", file=sys.stderr)
    print(f"Database updated with discord_url, discord_status, discord_members, twitter_username", file=sys.stderr)

if __name__ == "__main__":
    main()
