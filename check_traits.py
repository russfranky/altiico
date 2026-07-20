#!/usr/bin/env python3
"""Scrape NFT metadata to determine trait structure and uniqueness.

For each collection, fetches a few sample NFTs from the OpenSea API and checks:
  1. Number of traits per NFT (generative collections have many traits)
  2. Whether traits vary across NFTs (generative) or are identical (1/1 series)
  3. Whether each NFT has a unique name (1/1 art) or follows a numbered pattern
  4. Total unique trait combinations vs supply (uniqueness ratio)

Classifies collections as:
  - 'generative' — many traits, high variation (e.g., CyberBrokers, Meebits)
  - '1of1_series' — same trait structure but different values (e.g., DEyes Legends)
  - '1of1_art' — each NFT is unique art, few/no traits (e.g., Coldie 1/1s)
  - 'numbered' — simple numbered NFTs with minimal traits
  - 'unknown' — can't determine

Outputs:
  - os_scrape/trait_data.json
  - Updates vrm_index.db with trait_count, trait_types, nft_type, uniqueness_ratio
"""
import sqlite3, json, urllib.request, time, sys, re
from pathlib import Path
from collections import Counter

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"
KEY = open(__import__('os').path.expanduser('~/.opensea/api_key')).read().strip()

CHAIN_MAP = {
    'ethereum': 'ethereum', 'polygon': 'matic', 'base': 'base',
    'optimism': 'optimism', 'shape': 'shape', 'arbitrum': 'arbitrum',
    'ape_chain': 'apechain', 'zora': 'zora',
}

def os_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"X-API-KEY": KEY, "User-Agent": "vrm-scraper/8.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except:
            if attempt < 2: time.sleep(2)
            else: return None

def analyze_traits(nfts):
    """Analyze trait data from a list of NFTs (from OpenSea API)."""
    if not nfts:
        return None

    results = []
    all_trait_types = set()
    trait_value_sets = {}  # trait_type -> set of values seen

    for nft in nfts:
        traits = nft.get('traits', [])
        name = nft.get('name', '')
        trait_dict = {}
        for t in traits:
            tt = t.get('trait_type', '')
            tv = str(t.get('value', ''))
            trait_dict[tt] = tv
            all_trait_types.add(tt)
            if tt not in trait_value_sets:
                trait_value_sets[tt] = set()
            trait_value_sets[tt].add(tv)
        results.append({
            'id': nft.get('identifier', ''),
            'name': name,
            'trait_count': len(traits),
            'traits': trait_dict,
        })

    avg_traits = sum(r['trait_count'] for r in results) / len(results)
    num_trait_types = len(all_trait_types)

    # Check if names are unique (1/1 art) vs numbered pattern
    names = [r['name'] for r in results]
    unique_names = len(set(names))

    # Check if names follow a numbered pattern like "Meebit #14428" or "Boomboxhead #114"
    numbered_pattern = 0
    for name in names:
        if re.search(r'#\d+', name) or re.search(r'\b\d+/\d+\b', name):
            numbered_pattern += 1

    # Check trait variation: do different NFTs have different trait values?
    variation_score = 0
    for tt, values in trait_value_sets.items():
        if len(values) > 1:
            variation_score += 1
    variation_ratio = variation_score / max(num_trait_types, 1)

    # Check if all NFTs have the same trait count
    trait_counts = [r['trait_count'] for r in results]
    same_trait_count = len(set(trait_counts)) == 1

    # Classify
    if avg_traits == 0:
        nft_type = 'no_traits'
    elif avg_traits >= 5 and variation_ratio > 0.5:
        nft_type = 'generative'
    elif avg_traits >= 3 and variation_ratio > 0.3:
        nft_type = 'generative'
    elif avg_traits >= 2 and same_trait_count and variation_ratio > 0.3:
        nft_type = '1of1_series'  # Same structure, different values
    elif avg_traits <= 2 and unique_names == len(names) and numbered_pattern == 0:
        nft_type = '1of1_art'
    elif numbered_pattern / max(len(names), 1) > 0.5:
        nft_type = 'numbered'
    else:
        nft_type = 'mixed'

    # Uniqueness ratio: how many unique trait combos vs total NFTs sampled
    unique_combos = len(set(tuple(sorted(r['traits'].items())) for r in results))
    uniqueness_ratio = unique_combos / max(len(results), 1)

    return {
        'sample_size': len(results),
        'avg_traits': round(avg_traits, 1),
        'trait_types': num_trait_types,
        'trait_type_names': sorted(all_trait_types),
        'variation_ratio': round(variation_ratio, 2),
        'unique_names_ratio': round(unique_names / max(len(names), 1), 2),
        'numbered_ratio': round(numbered_pattern / max(len(names), 1), 2),
        'uniqueness_ratio': round(uniqueness_ratio, 2),
        'nft_type': nft_type,
        'sample_names': names[:5],
    }

def main():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # Get all collections with contracts
    collections = {}
    # 1. Collections with OpenSea slugs AND contracts
    for r in conn.execute("""
        SELECT c.id, c.name, c.opensea_slug, c.contract, c.chain, c.tier, c.total_supply
        FROM collections c
        WHERE c.opensea_slug IS NOT NULL AND c.opensea_slug != '' AND c.opensea_slug != '—'
        AND c.contract IS NOT NULL AND c.contract != '' AND c.contract != '—'
    """):
        slug = r['opensea_slug']
        if ' ' not in slug:
            collections[slug] = dict(r)
    # 2. Collections WITHOUT slugs but WITH contracts
    for r in conn.execute("""
        SELECT c.id, c.name, c.opensea_slug, c.contract, c.chain, c.tier, c.total_supply
        FROM collections c
        WHERE (c.opensea_slug IS NULL OR c.opensea_slug = '' OR c.opensea_slug = '—')
        AND c.contract IS NOT NULL AND c.contract != '' AND c.contract != '—'
    """):
        key = f"contract:{r['contract'][:10]}"
        if key not in collections:
            collections[key] = dict(r)
    # 3. OpenSea candidates
    for r in conn.execute("SELECT slug, name, contract, chain, total_supply FROM opensea_candidates WHERE slug IS NOT NULL AND slug != '' AND contract IS NOT NULL AND contract != ''"):
        if r['slug'] not in collections and ' ' not in r['slug']:
            collections[r['slug']] = {'id': r['slug'], 'name': r['name'] or r['slug'],
                                       'contract': r['contract'], 'chain': r['chain'] or 'ethereum',
                                       'tier': None, 'total_supply': r['total_supply']}
    conn.close()

    slugs = sorted(collections.keys())
    print(f"Scraping trait data for {len(slugs)} collections...", file=sys.stderr)

    results = {}
    SAMPLE_SIZE = 5  # Fetch 5 NFTs per collection for trait analysis

    for i, slug in enumerate(slugs):
        c = collections[slug]
        contract = c['contract']
        chain = c.get('chain', 'ethereum')
        os_chain = CHAIN_MAP.get(chain, 'ethereum')

        entry = {
            'slug': slug,
            'name': c['name'],
            'contract': contract,
            'chain': chain,
            'total_supply': c.get('total_supply'),
        }

        # Fetch sample NFTs
        nft_data = os_get(f"https://api.opensea.io/api/v2/chain/{os_chain}/contract/{contract}/nfts?limit={SAMPLE_SIZE}")
        if not nft_data or not nft_data.get('nfts'):
            entry['nft_type'] = 'unknown'
            entry['error'] = 'no NFTs returned'
            results[slug] = entry
            if (i+1) % 30 == 0:
                print(f"  [{i+1}/{len(slugs)}] processed", file=sys.stderr)
            time.sleep(0.15)
            continue

        nfts = nft_data['nfts']
        analysis = analyze_traits(nfts)
        if analysis:
            entry.update(analysis)

        results[slug] = entry

        if (i+1) % 30 == 0:
            types = Counter(e.get('nft_type', 'unknown') for e in results.values())
            print(f"  [{i+1}/{len(slugs)}] {dict(types)}", file=sys.stderr)

        time.sleep(0.15)

    # Save
    json.dump(results, open(BASE / "os_scrape" / "trait_data.json", "w"), indent=2)

    # Update DB
    conn = sqlite3.connect(str(DB))
    for col in ['collections', 'opensea_candidates']:
        for col_name, col_type in [('avg_traits', 'REAL'), ('trait_types_count', 'INTEGER'),
                                    ('nft_type', 'TEXT'), ('uniqueness_ratio', 'REAL'),
                                    ('trait_type_names', 'TEXT')]:
            try: conn.execute(f"ALTER TABLE {col} ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError: pass

    for slug, e in results.items():
        trait_names = json.dumps(e.get('trait_type_names', []))
        if slug.startswith('contract:'):
            contract_prefix = slug.split(':', 1)[1]
            conn.execute("""UPDATE collections SET
                avg_traits=?, trait_types_count=?, nft_type=?, uniqueness_ratio=?, trait_type_names=?
                WHERE contract LIKE ?""",
                (e.get('avg_traits'), e.get('trait_types'), e.get('nft_type'),
                 e.get('uniqueness_ratio'), trait_names, f"{contract_prefix}%"))
        else:
            for table, key_col in [('opensea_candidates', 'slug'), ('collections', 'opensea_slug')]:
                conn.execute(f"""UPDATE {table} SET
                    avg_traits=?, trait_types_count=?, nft_type=?, uniqueness_ratio=?, trait_type_names=?
                    WHERE {key_col}=?""",
                    (e.get('avg_traits'), e.get('trait_types'), e.get('nft_type'),
                     e.get('uniqueness_ratio'), trait_names, slug))
    conn.commit()
    conn.close()

    # Summary
    types = Counter(e.get('nft_type', 'unknown') for e in results.values())
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Trait data saved to os_scrape/trait_data.json", file=sys.stderr)
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        icon = {'generative': '🎲', '1of1_series': '🎨', '1of1_art': '🖼',
                'numbered': '🔢', 'no_traits': '∅', 'mixed': '🔀', 'unknown': '❓'}.get(t, '?')
        print(f"  {icon} {t:<20} {count}", file=sys.stderr)

    # Print Tier A/B details
    print(f"\nTier A/B collections:", file=sys.stderr)
    for slug, e in sorted(results.items()):
        c = collections.get(slug, {})
        if c.get('tier') in ('A', 'B'):
            icon = {'generative': '🎲', '1of1_series': '🎨', '1of1_art': '🖼',
                    'numbered': '🔢', 'no_traits': '∅', 'mixed': '🔀', 'unknown': '❓'}.get(e.get('nft_type'), '?')
            avg_t = e.get('avg_traits', '?')
            types_n = e.get('trait_types', '?')
            uniq = e.get('uniqueness_ratio', '?')
            print(f"  {icon} {e['name'][:35]:36s} type={e.get('nft_type','?'):<14} avg_traits={str(avg_t):>4} types={str(types_n):>3} uniq={uniq}", file=sys.stderr)

if __name__ == "__main__":
    main()
