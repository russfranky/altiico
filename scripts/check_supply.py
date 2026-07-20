#!/usr/bin/env python3
"""Determine mint supply status for all collections.

Strategy:
  1. Get total_supply + unique_item_count + description from OpenSea API
  2. Try reading maxSupply()/totalSupply() from contracts via public RPC
  3. Parse description for supply numbers (e.g., "10,001 unique", "420 supply")
  4. Compare total_supply vs parsed max to determine: capped, ongoing, or unknown

Outputs:
  - os_scrape/supply_data.json (updated with mint_status, max_supply, description_parsed)
  - Updates vrm_index.db
"""
import sqlite3, json, urllib.request, time, sys, re
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"
KEY = open(__import__('os').path.expanduser('~/.opensea/api_key')).read().strip()

RPCS = {
    'ethereum': 'https://ethereum.publicnode.com',
    'polygon': 'https://polygon-bor-rpc.publicnode.com',
    'base': 'https://base-rpc.publicnode.com',
    'optimism': 'https://optimism-rpc.publicnode.com',
    'shape': 'https://shape-rpc.publicnode.com',
    'arbitrum': 'https://arbitrum-one-rpc.publicnode.com',
    'ape_chain': 'https://apechain.calderachain.xyz/http',
    'zora': 'https://zora-rpc.publicnode.com',
}

def os_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"X-API-KEY": KEY, "User-Agent": "vrm-scraper/7.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except:
            if attempt < 2: time.sleep(2)
            else: return None

def rpc_call(rpc_url, to, data, timeout=10):
    payload = json.dumps({
        "jsonrpc": "2.0", "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"], "id": 1
    }).encode()
    req = urllib.request.Request(rpc_url, data=payload, headers={
        "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.load(r)
            if result.get('result') and result['result'] != '0x':
                return int(result['result'], 16)
    except:
        pass
    return None

# Common max supply function selectors
MAX_SUPPLY_SELECTORS = {
    'maxSupply()': '0xd5ab39dc',
    'collectionSize()': '0x06f45a2d',
    'getMaxSupply()': '0x0e113c4b',
    'MAX_SUPPLY()': '0x06661abd',
    'cap()': '0x35587ea9',
    'maximumSupply()': '0x4d230a40',
    'totalMaxSupply()': '0xb19f8ca5',
    'maxItems()': '0x4d562d0a',
}

def parse_description_for_supply(desc):
    """Parse collection description for supply numbers."""
    if not desc: return None
    # Patterns ordered by specificity — most specific first
    patterns = [
        # "80 VRM Avatars" / "10,001 CyberBrokers" / "4,200 Squaddies"
        r'(\d[\d,]+)\s*(?:VRM\s+Avatars|Avatars|NFTs|Heroes|Mechs|Wizards|Chibis|Squaddies|Brokers|Punks|Bears|Birds)',
        # "10,001 unique and on-chain CyberBroker NFTs" / "10,000 unique Wizard NFTs"
        r'(\d[\d,]+)\s*unique\s+[^.]*?(?:NFTs|characters|avatars|pieces|items)',
        # "20,000 unique 3D voxel characters" / "collection of 20,000 unique"
        r'(\d[\d,]+)\s*unique\s+\w+',
        # "420 supply" / "5,000 generative" / "100 pieces"
        r'(\d[\d,]+)\s*(?:supply|total supply|max supply|generative|pieces|items|tokens)',
        # "supply of 420" / "total of 5000"
        r'(?:supply\s*(?:of|is)?|total\s*(?:of)?|max\s*supply\s*(?:of|is)?)\s*(\d[\d,]+)',
        # "collection of 20,000" / "set of 10,000"
        r'(?:collection\s+of|set\s+of)\s+(\d[\d,]+)',
    ]
    for p in patterns:
        for m in re.finditer(p, desc, re.IGNORECASE):
            num_str = m.group(1).replace(',', '')
            try:
                num = int(num_str)
                # Exclude years (2000-2030) unless clearly a supply number
                if 2000 <= num <= 2030:
                    start = max(0, m.start() - 20)
                    context = desc[start:m.end() + 10]
                    if re.search(r'(?:Christmas|year|©|class of|since|Collection)\s*' + str(num), context, re.IGNORECASE):
                        continue
                if num >= 10:
                    return num
            except:
                pass
    # Handle "10k" style
    m = re.search(r'(\d+)k\s*(?:unique|supply|collection|pieces|items|NFTs|avatars)', desc, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 1000
    return None

def main():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    collections = {}
    # 1. Collections with OpenSea slugs
    for r in conn.execute("""
        SELECT c.id, c.name, c.opensea_slug, c.contract, c.chain, c.tier
        FROM collections c WHERE c.opensea_slug IS NOT NULL AND c.opensea_slug != '' AND c.opensea_slug != '—'
    """):
        slug = r['opensea_slug']
        if ' ' not in slug:
            collections[slug] = dict(r)
    # 2. OpenSea candidates
    for r in conn.execute("SELECT slug, name, contract, chain FROM opensea_candidates WHERE slug IS NOT NULL AND slug != ''"):
        if r['slug'] not in collections and ' ' not in r['slug']:
            collections[r['slug']] = {'id': r['slug'], 'name': r['name'] or r['slug'],
                                       'contract': r['contract'], 'chain': r['chain'] or 'ethereum', 'tier': None}
    # 3. Collections WITHOUT slugs but WITH contracts — use contract-derived key
    for r in conn.execute("""
        SELECT c.id, c.name, c.opensea_slug, c.contract, c.chain, c.tier
        FROM collections c
        WHERE (c.opensea_slug IS NULL OR c.opensea_slug = '' OR c.opensea_slug = '—')
        AND c.contract IS NOT NULL AND c.contract != '' AND c.contract != '—'
    """):
        contract = r['contract']
        key = f"contract:{contract[:10]}"
        if key not in collections:
            collections[key] = dict(r)
            collections[key]['_no_slug'] = True
    conn.close()

    slugs = sorted(collections.keys())
    print(f"Fetching supply data for {len(slugs)} collections...", file=sys.stderr)

    results = {}
    for i, slug in enumerate(slugs):
        c = collections[slug]
        entry = {
            'slug': slug, 'name': c['name'],
            'total_supply': None, 'unique_item_count': None,
            'max_supply': None, 'max_supply_source': None,
            'mint_status': 'unknown', 'mint_progress': None,
            'description': '',
        }

        # 1. OpenSea API — by slug or by contract
        no_slug = c.get('_no_slug', False)
        cd = None
        if not no_slug:
            cd = os_get(f"https://api.opensea.io/api/v2/collections/{slug}")
        else:
            # No slug — resolve slug from contract via NFTs endpoint
            contract = c.get('contract')
            chain = c.get('chain', 'ethereum')
            os_chain = {'polygon':'matic','base':'base','optimism':'optimism','shape':'shape','arbitrum':'arbitrum','ape_chain':'apechain'}.get(chain, chain)
            nft_data = os_get(f"https://api.opensea.io/api/v2/chain/{os_chain}/contract/{contract}/nfts?limit=1")
            if nft_data and nft_data.get('nfts'):
                resolved_slug = nft_data['nfts'][0].get('collection', '')
                if resolved_slug:
                    cd = os_get(f"https://api.opensea.io/api/v2/collections/{resolved_slug}")
                    entry['_resolved_slug'] = resolved_slug
            time.sleep(0.15)
        if cd:
            entry['total_supply'] = cd.get('total_supply')
            entry['unique_item_count'] = cd.get('unique_item_count')
            entry['description'] = cd.get('description', '') or ''
        time.sleep(0.15)

        # 2. Try RPC for maxSupply
        contract = c.get('contract')
        chain = c.get('chain', 'ethereum')
        if contract and len(contract) >= 20 and chain in RPCS:
            rpc = RPCS[chain]
            for name, sel in MAX_SUPPLY_SELECTORS.items():
                val = rpc_call(rpc, contract, sel)
                if val is not None and val > 0:
                    entry['max_supply'] = val
                    entry['max_supply_source'] = f'contract:{name}'
                    break
            time.sleep(0.05)

        # 3. Parse description for supply number
        if entry['max_supply'] is None:
            parsed = parse_description_for_supply(entry['description'])
            if parsed:
                entry['max_supply'] = parsed
                entry['max_supply_source'] = 'description'

        # 4. Determine mint status
        total = entry['total_supply']
        max_s = entry['max_supply']
        if max_s is not None and total is not None:
            if total >= max_s:
                entry['mint_status'] = 'capped'
            elif total > 0 and max_s > 0:
                entry['mint_status'] = 'ongoing'
                entry['mint_progress'] = round(total / max_s * 100, 1)
        elif total is not None and total > 0:
            # No max supply found — use age heuristic
            created = cd.get('created_date', '') if cd else ''
            if created:
                from datetime import datetime, date
                try:
                    created_date = datetime.strptime(created[:10], '%Y-%m-%d').date()
                    age_days = (date.today() - created_date).days
                    if age_days > 365:
                        entry['mint_status'] = 'likely_capped'
                        entry['mint_note'] = f'created {age_days}d ago, no maxSupply found'
                    else:
                        entry['mint_status'] = 'no_max_supply'
                        entry['mint_note'] = f'created {age_days}d ago'
                except:
                    entry['mint_status'] = 'no_max_supply'
            else:
                entry['mint_status'] = 'no_max_supply'

        results[slug] = entry

        if (i+1) % 30 == 0:
            capped = sum(1 for e in results.values() if e['mint_status'] == 'capped')
            ongoing = sum(1 for e in results.values() if e['mint_status'] == 'ongoing')
            print(f"  [{i+1}/{len(slugs)}] capped: {capped}, ongoing: {ongoing}", file=sys.stderr)

    # Save
    json.dump(results, open(BASE / "data" / "os_scrape" / "supply_data.json", "w"), indent=2)

    # Update DB
    conn = sqlite3.connect(str(DB))
    for col in ['collections', 'opensea_candidates']:
        for col_name, col_type in [('total_supply','INTEGER'),('max_supply','INTEGER'),
                                    ('mint_status','TEXT'),('mint_progress','REAL'),
                                    ('max_supply_source','TEXT')]:
            try: conn.execute(f"ALTER TABLE {col} ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError: pass

    for slug, e in results.items():
        if slug.startswith('contract:'):
            contract_prefix = slug.split(':', 1)[1]
            conn.execute("""UPDATE collections SET
                total_supply=?, max_supply=?, mint_status=?, mint_progress=?, max_supply_source=?
                WHERE contract LIKE ?""",
                (e['total_supply'], e['max_supply'], e['mint_status'],
                 e.get('mint_progress'), e.get('max_supply_source'), f"{contract_prefix}%"))
        else:
            for table, key_col in [('opensea_candidates', 'slug'), ('collections', 'opensea_slug')]:
                conn.execute(f"""UPDATE {table} SET
                    total_supply=?, max_supply=?, mint_status=?, mint_progress=?, max_supply_source=?
                    WHERE {key_col}=?""",
                    (e['total_supply'], e['max_supply'], e['mint_status'],
                     e.get('mint_progress'), e.get('max_supply_source'), slug))
    conn.commit()
    conn.close()

    # Summary
    capped = sum(1 for e in results.values() if e['mint_status'] == 'capped')
    likely = sum(1 for e in results.values() if e['mint_status'] == 'likely_capped')
    ongoing = sum(1 for e in results.values() if e['mint_status'] == 'ongoing')
    no_max = sum(1 for e in results.values() if e['mint_status'] == 'no_max_supply')
    unknown = sum(1 for e in results.values() if e['mint_status'] == 'unknown')

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  🔒 Capped (mint complete):       {capped}", file=sys.stderr)
    print(f"  🔒 Likely capped (>1yr old):     {likely}", file=sys.stderr)
    print(f"  🟢 Ongoing (still minting):      {ongoing}", file=sys.stderr)
    print(f"  ❓ No maxSupply (<1yr old):      {no_max}", file=sys.stderr)
    print(f"  ❓ Unknown:                      {unknown}", file=sys.stderr)

    # Print Tier A/B details
    print(f"\nTier A/B collections:", file=sys.stderr)
    for slug, e in sorted(results.items()):
        c = collections.get(slug, {})
        if c.get('tier') in ('A', 'B'):
            icon = {'capped': '🔒', 'likely_capped': '🔒', 'ongoing': '🟢',
                    'no_max_supply': '❓', 'unknown': '❓'}.get(e['mint_status'], '?')
            total = e['total_supply'] or '?'
            max_s = e['max_supply'] or '?'
            src = e.get('max_supply_source', '') or ''
            progress = f" ({e.get('mint_progress',0)}%)" if e['mint_status'] == 'ongoing' else ''
            likely_mark = '~' if e['mint_status'] == 'likely_capped' else ''
            print(f"  {icon} {e['name'][:35]:36s} total={str(total):>6} max={str(max_s)+likely_mark:>6} [{src}]{progress}", file=sys.stderr)

if __name__ == "__main__":
    main()
