#!/usr/bin/env python3
"""Build a searchable SQLite database + static HTML catalog from all VRM data sources.

Sources:
  - vrm_collections.md (tier tables + licensing index, parsed)
  - toxsam_projects.json (8 projects with license info)
  - toxsam_*.json (per-project avatar manifests, ~4000 avatars)
  - os_scrape/known_vrm_verified.json (19 verified known VRM collections)
  - os_scrape/vrm_check_results.json (202 OpenSea candidates)
  - os_scrape/q_*.json (OpenSea search results)

Outputs:
  - vrm_index.db (SQLite database)
  - index.html (static searchable catalog, client-side, no server)
"""
import json, re, sqlite3, os, glob, html, hashlib, sys
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "data" / "vrm_index.db"
HTML_PATH = BASE / "static" / "index.html"

def _is_video_url(url):
    """Detect video URLs that can't be used in <img> tags."""
    if not url:
        return False
    u = url.lower()
    return '.mp4' in u or 'stream.mux.com' in u or '.webm' in u or '.mov' in u

def _img(url):
    """Return url if it's a usable image, else empty string."""
    return url if url and not _is_video_url(url) else ''

# ─── Schema ──────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE collections (
    id TEXT PRIMARY KEY,           -- slug or derived id
    name TEXT NOT NULL,
    tier TEXT,                     -- A, B, C, not_vrm, arweave, infra
    chain TEXT,                    -- primary chain (ethereum, base, optimism, polygon, shape, solana, arweave, multi)
    contract TEXT,                 -- primary contract (hex address or null); see contracts table for all
    opensea_slug TEXT,
    release_date TEXT,             -- ISO date from OpenSea created_date
    vrm_param TEXT,                -- vrm_url, vrm, avatar_url, asset, files, model/vrm, or null
    vrm_url_pattern TEXT,          -- sample VRM URL pattern
    license_category TEXT,         -- green, yellow, red, unknown
    vrm_license TEXT,              -- CC0, CC_BY, Redistribution_Prohibited, Other, etc.
    commercial_use TEXT,           -- Allow, Disallow, unknown
    allowed_user TEXT,             -- Everyone, ExplicitlyLicensedPerson, OnlyAuthor, unknown
    redistribution TEXT,           -- Allow, Prohibited, unknown
    avatar_count INTEGER,
    creator TEXT,
    description TEXT,
    notes TEXT,
    source TEXT,                   -- opensea, toxsam, curated, hackmd, etc.
    url_status TEXT,               -- alive, dead, error
    wayback_available INTEGER,
    wayback_snapshots INTEGER,
    wayback_url TEXT,
    discord_url TEXT,
    discord_status TEXT,           -- alive, dead, rate_limited, error, none
    discord_members INTEGER,
    twitter_username TEXT,
    image_url TEXT,                -- collection image from OpenSea
    banner_image_url TEXT,
    sample_nft_image TEXT,         -- sample NFT preview image
    sample_nft_name TEXT,
    vrm_url_https TEXT,            -- VRM URL converted to HTTPS gateway
    total_supply INTEGER,          -- current minted supply
    max_supply INTEGER,            -- max supply (from contract or description)
    mint_status TEXT,              -- capped, likely_capped, ongoing, no_max_supply, unknown
    mint_progress REAL,            -- % minted (if ongoing)
    max_supply_source TEXT,        -- contract:maxSupply(), description, etc.
    avg_traits REAL,               -- average traits per NFT
    trait_types_count INTEGER,     -- number of distinct trait types
    nft_type TEXT,                 -- generative, 1of1_series, 1of1_art, numbered, no_traits, mixed
    uniqueness_ratio REAL,         -- ratio of unique trait combos in sample
    trait_type_names TEXT,         -- JSON array of trait type names
    project_url TEXT,              -- official project website
    sample_metadata_url TEXT,      -- sample NFT metadata URL
    -- OpenSea API sweep fields
    num_owners INTEGER,            -- unique wallet holders
    floor_price REAL,              -- current floor price
    floor_price_symbol TEXT,       -- floor price currency (ETH, etc.)
    total_volume REAL,             -- total trading volume
    total_sales INTEGER,           -- total sales count
    category TEXT,                 -- OpenSea category (pfps, gaming, art, etc.)
    safelist_status TEXT,          -- verified, approved, not_requested
    owner_address TEXT,            -- collection owner/creator address
    royalty_fee REAL,              -- royalty percentage
    royalty_recipient TEXT,        -- royalty recipient address
    instagram_username TEXT,       -- Instagram handle
    telegram_url TEXT,             -- Telegram group URL
    is_nsfw INTEGER,               -- NSFW flag
    rarity_strategy TEXT,          -- rarity strategy (openrarity, etc.)
    unique_item_count INTEGER,     -- unique NFT count
    one_day_volume REAL,           -- 24h volume
    one_day_sales INTEGER,         -- 24h sales
    seven_day_volume REAL,         -- 7d volume
    seven_day_sales INTEGER,       -- 7d sales
    thirty_day_volume REAL,        -- 30d volume
    thirty_day_sales INTEGER       -- 30d sales
);

CREATE TABLE contracts (
    collection_id TEXT,
    address TEXT NOT NULL,
    chain TEXT NOT NULL,
    token_standard TEXT,           -- ERC-721, ERC-1155, etc.
    is_primary INTEGER DEFAULT 0,
    FOREIGN KEY (collection_id) REFERENCES collections(id),
    PRIMARY KEY (collection_id, address)
);

CREATE TABLE avatars (
    id TEXT PRIMARY KEY,
    collection_id TEXT,
    name TEXT,
    description TEXT,
    model_file_url TEXT,
    format TEXT,
    thumbnail_url TEXT,
    is_public INTEGER,
    metadata_json TEXT,
    FOREIGN KEY (collection_id) REFERENCES collections(id)
);

CREATE TABLE opensea_candidates (
    slug TEXT PRIMARY KEY,
    name TEXT,
    chain TEXT,
    contract TEXT,
    release_date TEXT,             -- ISO date from OpenSea created_date
    status TEXT,                   -- vrm, no_vrm, mentions, error
    vrm_param TEXT,
    vrm_url TEXT,
    sample_nft TEXT,
    metadata_url TEXT,
    source_query TEXT,
    url_status TEXT,               -- alive, dead, error (from check_opensea_urls.py)
    wayback_available INTEGER,     -- 1 if Wayback Machine has a snapshot
    wayback_snapshots INTEGER,     -- number of snapshots
    wayback_url TEXT,
    discord_url TEXT,
    discord_status TEXT,
    discord_members INTEGER,
    twitter_username TEXT,
    image_url TEXT,
    banner_image_url TEXT,
    sample_nft_image TEXT,
    sample_nft_name TEXT,
    vrm_url_https TEXT,
    total_supply INTEGER,
    max_supply INTEGER,
    mint_status TEXT,
    mint_progress REAL,
    max_supply_source TEXT,
    avg_traits REAL,
    trait_types_count INTEGER,
    nft_type TEXT,
    uniqueness_ratio REAL,
    trait_type_names TEXT
);

CREATE TABLE sources (
    id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    type TEXT                      -- registry, api, manifest, markdown
);
"""

# ─── Helpers ─────────────────────────────────────────────────────────────────

def slugify(name):
    s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return s or hashlib.md5(name.encode()).hexdigest()[:12]

def base_name(name):
    """Strip parenthetical suffixes for fuzzy matching: 'Halloween Rising (VRM file)' → 'Halloween Rising'"""
    return re.sub(r'\s*\([^)]*\)\s*', '', name).strip()

def parse_md_table(lines, start_idx):
    """Parse a markdown table starting at start_idx. Returns (rows, next_idx)."""
    rows = []
    i = start_idx
    # Skip header and separator
    while i < len(lines) and not lines[i].strip().startswith('|'):
        i += 1
    if i >= len(lines): return rows, i
    header = [c.strip() for c in lines[i].strip().split('|') if c.strip()]
    i += 1
    if i < len(lines) and lines[i].strip().startswith('|---') or '---' in lines[i]:
        i += 1
    # Data rows
    while i < len(lines) and lines[i].strip().startswith('|'):
        cells = [c.strip() for c in lines[i].strip().split('|') if c.strip()]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
        i += 1
    return rows, i

def clean_contract(s):
    """Extract first 0x... address from a string."""
    if not s: return None
    m = re.search(r'(0x[a-fA-F0-9]{40})', s)
    return m.group(1) if m else None

# ─── Parse vrm_collections.md ────────────────────────────────────────────────

def parse_markdown():
    """Parse the tier tables and licensing tables from vrm_collections.md."""
    lines = (BASE / "data" / "vrm_collections.md").read_text().split('\n')
    collections = []

    # Map section headers to tier + chain
    section_map = {
        '### Ethereum mainnet': ('A', 'ethereum'),
        '### Base': ('A', 'base'),
        '### Optimism': ('A', 'optimism'),
        '### Polygon': ('A', 'polygon'),
        '### Shape / other L2s': ('A', 'shape'),
    }
    tier_b_sections = {
        '### Ethereum mainnet': ('B', 'ethereum'),
        '### Ethereum / Base (multi-chain)': ('B', 'multi'),
        '### Polygon': ('B', 'polygon'),
    }

    i = 0
    current_tier = None
    current_chain = None
    in_tier_b = False

    while i < len(lines):
        line = lines[i].strip()

        # Detect tier sections
        if line.startswith('## Tier A'):
            current_tier = 'A'
            in_tier_b = False
        elif line.startswith('## Tier B'):
            current_tier = 'B'
            in_tier_b = True
        elif line.startswith('## Tier C'):
            current_tier = 'C'
            in_tier_b = False
        elif line.startswith('## Not VRM'):
            current_tier = 'not_vrm'
        elif line.startswith('## Non-Ethereum'):
            current_tier = 'infra'
        elif line.startswith('## Arweave-native'):
            current_tier = 'arweave'

        # Detect subsections
        if current_tier == 'A' and line in section_map:
            t, c = section_map[line]
            rows, i = parse_md_table(lines, i + 1)
            for r in rows:
                slug = r.get('OpenSea slug', r.get('Collection', '')).replace('†', '').strip()
                if slug == '—' or not slug: slug = None
                name = r.get('Collection', r.get('name', ''))
                contract = clean_contract(r.get('Contract', ''))
                vrm_param = re.sub(r'`([^`]+)`', r'\1', r.get('Metadata param', r.get('vrm_param', '')))
                vrm_url = r.get('Sample VRM URL', r.get('vrm_url', ''))
                notes = r.get('Notes', '')
                collections.append({
                    'id': slug or slugify(name),
                    'name': name,
                    'tier': 'A',
                    'chain': c,
                    'contract': contract,
                    'opensea_slug': slug if slug and slug != '—' else None,
                    'vrm_param': vrm_param or None,
                    'vrm_url_pattern': vrm_url if vrm_url != '—' else None,
                    'notes': notes,
                    'source': 'curated+verified',
                })
            continue

        if current_tier == 'B' and line in tier_b_sections:
            t, c = tier_b_sections[line]
            rows, i = parse_md_table(lines, i + 1)
            for r in rows:
                name = r.get('Collection', '')
                contract = clean_contract(r.get('Contract', ''))
                notes = r.get('Notes', '')
                collections.append({
                    'id': slugify(name),
                    'name': name,
                    'tier': 'B',
                    'chain': c,
                    'contract': contract,
                    'opensea_slug': None,
                    'vrm_param': None,
                    'vrm_url_pattern': None,
                    'notes': notes,
                    'source': 'curated',
                })
            continue

        # Tier C table
        if current_tier == 'C' and line.startswith('| Collection'):
            rows, i = parse_md_table(lines, i + 1)
            for r in rows:
                name = r.get('Collection', '')
                opensea = r.get('OpenSea', '')
                notes = r.get('Notes', '')
                collections.append({
                    'id': slugify(name),
                    'name': name,
                    'tier': 'C',
                    'chain': 'unknown',
                    'contract': clean_contract(opensea),
                    'opensea_slug': None,
                    'vrm_param': None,
                    'vrm_url_pattern': None,
                    'notes': notes,
                    'source': 'curated',
                })
            continue

        # Arweave-native table
        if current_tier == 'arweave' and line.startswith('| Project'):
            rows, i = parse_md_table(lines, i + 1)
            for r in rows:
                name = r.get('Project', r.get('name', ''))
                collections.append({
                    'id': slugify(name),
                    'name': name,
                    'tier': 'arweave',
                    'chain': 'arweave',
                    'contract': None,
                    'opensea_slug': None,
                    'vrm_param': None,
                    'vrm_url_pattern': r.get('VRM URL', r.get('model_file_url', '')),
                    'avatar_count': int(r['Avatars']) if r.get('Avatars', '').isdigit() else None,
                    'creator': r.get('Creator', ''),
                    'notes': r.get('Notes', ''),
                    'source': 'toxsam',
                })
            continue

        # Infra table
        if current_tier == 'infra' and line.startswith('| Platform'):
            rows, i = parse_md_table(lines, i + 1)
            for r in rows:
                name = r.get('Platform', '')
                collections.append({
                    'id': slugify(name),
                    'name': name,
                    'tier': 'infra',
                    'chain': r.get('Chain', '').lower(),
                    'contract': None,
                    'opensea_slug': None,
                    'vrm_param': None,
                    'vrm_url_pattern': None,
                    'notes': r.get('Notes', ''),
                    'source': 'curated',
                })
            continue

        # Licensing tables
        if line == '### 🟢 No permission needed (CC0 / public domain)':
            rows, i = parse_md_table(lines, i + 1)
            for r in rows:
                name = r.get('Collection', '')
                # Match to existing collection by name
                slug = slugify(name)
                for c in collections:
                    if slugify(c['name']) == slug or c['name'] == name or slugify(base_name(c['name'])) == slug or slugify(base_name(name)) == slugify(c['name']) or slugify(base_name(name)) == slugify(base_name(c['name'])) or slug in slugify(c['name']) or slugify(c['name']) in slug:
                        c['license_category'] = 'green'
                        c['vrm_license'] = r.get('VRM license', '')
                        c['commercial_use'] = 'Allow'
                        c['allowed_user'] = 'Everyone'
                        c['redistribution'] = 'Allow'
                        break
                else:
                    collections.append({
                        'id': slug, 'name': name, 'tier': 'unknown',
                        'license_category': 'green',
                        'vrm_license': r.get('VRM license', ''),
                        'commercial_use': 'Allow',
                        'allowed_user': 'Everyone',
                        'redistribution': 'Allow',
                        'source': 'licensing-index',
                    })
            continue

        if line == '### 🟡 Permission needed — holder-based commercial license':
            rows, i = parse_md_table(lines, i + 1)
            for r in rows:
                name = r.get('Collection', '')
                slug = slugify(name)
                for c in collections:
                    if slugify(c['name']) == slug or c['name'] == name or slugify(base_name(c['name'])) == slug or slugify(base_name(name)) == slugify(c['name']) or slugify(base_name(name)) == slugify(base_name(c['name'])) or slug in slugify(c['name']) or slugify(c['name']) in slug:
                        c['license_category'] = 'yellow'
                        c['vrm_license'] = r.get('VRM license', '')
                        c['commercial_use'] = r.get('Commercial', '')
                        c['allowed_user'] = r.get('Avatar use by', '')
                        c['notes'] = (c.get('notes') or '') + ' | ' + r.get('Notes', '')
                        break
                else:
                    collections.append({
                        'id': slug, 'name': name, 'tier': 'unknown',
                        'license_category': 'yellow',
                        'vrm_license': r.get('VRM license', ''),
                        'commercial_use': r.get('Commercial', ''),
                        'allowed_user': r.get('Avatar use by', ''),
                        'notes': r.get('Notes', ''),
                        'source': 'licensing-index',
                    })
            continue

        if line == '### 🔴 Permission required — all rights reserved / no commercial use':
            rows, i = parse_md_table(lines, i + 1)
            for r in rows:
                name = r.get('Collection', '')
                slug = slugify(name)
                for c in collections:
                    if slugify(c['name']) == slug or c['name'] == name or slugify(base_name(c['name'])) == slug or slugify(base_name(name)) == slugify(c['name']) or slugify(base_name(name)) == slugify(base_name(c['name'])) or slug in slugify(c['name']) or slugify(c['name']) in slug:
                        c['license_category'] = 'red'
                        c['vrm_license'] = r.get('VRM license', '')
                        c['commercial_use'] = r.get('Commercial', '')
                        c['allowed_user'] = r.get('Avatar use by', '')
                        c['notes'] = (c.get('notes') or '') + ' | ' + r.get('Notes', '')
                        break
                else:
                    collections.append({
                        'id': slug, 'name': name, 'tier': 'unknown',
                        'license_category': 'red',
                        'vrm_license': r.get('VRM license', ''),
                        'commercial_use': r.get('Commercial', ''),
                        'allowed_user': r.get('Avatar use by', ''),
                        'notes': r.get('Notes', ''),
                        'source': 'licensing-index',
                    })
            continue

        i += 1

    return collections

# ─── Parse ToxSam projects + avatars ─────────────────────────────────────────

def parse_toxsam():
    """Parse toxsam_projects.json and per-project avatar manifests."""
    projects = json.load(open(BASE / "data" / "cache" / "toxsam_projects.json"))
    avatars = []

    for p in projects:
        pid = p['id']
        avatar_file = BASE / f"toxsam_{pid}.json"
        if avatar_file.exists():
            data = json.load(open(avatar_file))
            avatar_list = data if isinstance(data, list) else data.get('avatars', data.get('items', []))
            for a in avatar_list:
                avatars.append({
                    'id': a.get('id', hashlib.md5(str(a.get('model_file_url','')).encode()).hexdigest()[:12]),
                    'collection_id': pid,
                    'name': a.get('name', ''),
                    'description': a.get('description', ''),
                    'model_file_url': a.get('model_file_url', ''),
                    'format': a.get('format', 'VRM'),
                    'thumbnail_url': a.get('thumbnail_url', ''),
                    'is_public': 1 if a.get('is_public', True) else 0,
                    'metadata_json': json.dumps(a.get('metadata', {})),
                })

    return projects, avatars

# ─── Parse OpenSea data ──────────────────────────────────────────────────────

def parse_opensea():
    """Parse OpenSea scrape results."""
    candidates = []

    # vrm_check_results.json
    vcr_path = BASE / "data" / "os_scrape" / "vrm_check_results.json"
    if vcr_path.exists():
        d = json.load(open(vcr_path))
        for e in d.get('vrm', []):
            candidates.append({
                'slug': e['slug'], 'name': e.get('name', ''), 'chain': 'ethereum',
                'contract': None, 'status': 'vrm',
                'vrm_param': e.get('vrm_param', ''), 'vrm_url': e.get('vrm_url', ''),
                'sample_nft': e.get('sample_nft', ''), 'metadata_url': e.get('metadata_url', ''),
                'source_query': 'opensea-scrape',
            })
        for e in d.get('no_vrm', []):
            candidates.append({
                'slug': e['slug'], 'name': e.get('name', ''), 'chain': 'ethereum',
                'contract': None, 'status': 'no_vrm',
                'vrm_param': '', 'vrm_url': '',
                'sample_nft': e.get('sample_nft', ''), 'metadata_url': e.get('metadata_url', ''),
                'source_query': 'opensea-scrape',
            })
        for e in d.get('mentions', []):
            candidates.append({
                'slug': e['slug'], 'name': e.get('name', ''), 'chain': 'ethereum',
                'contract': None, 'status': 'mentions',
                'vrm_param': '', 'vrm_url': '',
                'sample_nft': e.get('sample_nft', ''), 'metadata_url': e.get('metadata_url', ''),
                'source_query': 'opensea-scrape',
            })

    # known_vrm_verified.json
    kv_path = BASE / "data" / "os_scrape" / "known_vrm_verified.json"
    if kv_path.exists():
        d = json.load(open(kv_path))
        for e in d:
            slug = e['slug']
            # Update existing candidate or add new
            existing = next((c for c in candidates if c['slug'] == slug), None)
            if existing:
                existing['chain'] = e.get('os_chain', existing['chain'])
                existing['contract'] = e.get('contract', '')
                existing['status'] = 'vrm' if e.get('vrm_url') else 'no_vrm'
                existing['vrm_param'] = e.get('vrm_param', '')
                existing['vrm_url'] = e.get('vrm_url', '')
            else:
                candidates.append({
                    'slug': slug, 'name': e.get('os_name', ''), 'chain': e.get('os_chain', 'ethereum'),
                    'contract': e.get('contract', ''), 'status': 'vrm' if e.get('vrm_url') else 'no_vrm',
                    'vrm_param': e.get('vrm_param', ''), 'vrm_url': e.get('vrm_url', ''),
                    'sample_nft': '', 'metadata_url': '', 'source_query': 'known-vrm',
                })

    # Search result files — collect all unique slugs with their query source
    for f in sorted(glob.glob(str(BASE / "data" / "os_scrape" / "q_*.json"))):
        query = Path(f).stem.replace('q_', '')
        d = json.load(open(f))
        for r in d.get('results', []):
            if r.get('type') == 'collection':
                c = r.get('collection') or {}
                slug = c.get('collection')
                if not slug: continue
                existing = next((x for x in candidates if x['slug'] == slug), None)
                if existing:
                    if query not in existing['source_query']:
                        existing['source_query'] += f',{query}'
                else:
                    candidates.append({
                        'slug': slug, 'name': c.get('name', ''), 'chain': 'ethereum',
                        'contract': None, 'status': 'not_checked',
                        'vrm_param': '', 'vrm_url': '',
                        'sample_nft': '', 'metadata_url': '',
                        'source_query': query,
                    })

    return candidates

# ─── Parse URL status ────────────────────────────────────────────────────────

def parse_url_status():
    """Load opensea_url_status.json and return a slug→status map."""
    path = BASE / "opensea_url_status.json"
    if not path.exists():
        return {}
    d = json.load(open(path))
    return {r['slug']: r for r in d}

# ─── Parse OpenSea collection details (release dates + contracts) ────────────

def parse_collection_details():
    """Load os_scrape/collection_details.json — release dates and all contracts per collection."""
    path = BASE / "data" / "os_scrape" / "collection_details.json"
    if not path.exists():
        return {}
    d = json.load(open(path))
    return d

# ─── Parse social links + Discord status ─────────────────────────────────────

def parse_social_links():
    """Load os_scrape/social_links.json and discord_status.json."""
    social_path = BASE / "data" / "os_scrape" / "social_links.json"
    discord_path = BASE / "data" / "os_scrape" / "discord_status.json"
    social = json.load(open(social_path)) if social_path.exists() else {}
    discord = json.load(open(discord_path)) if discord_path.exists() else {}
    return social, discord

# ─── Parse preview images ────────────────────────────────────────────────────

def parse_preview_images():
    """Load os_scrape/preview_images.json — collection images, sample NFT images, VRM HTTPS URLs."""
    path = BASE / "data" / "os_scrape" / "preview_images.json"
    if not path.exists():
        return {}
    return json.load(open(path))

# ─── Parse collection meta (OpenSea API sweep) ───────────────────────────────

def parse_collection_meta():
    """Load os_scrape/collection_meta.json — descriptions, num_owners, floor_price, etc."""
    path = BASE / "data" / "os_scrape" / "collection_meta.json"
    if not path.exists():
        return {}
    return json.load(open(path))

# ─── Parse supply data ───────────────────────────────────────────────────────

def parse_supply_data():
    """Load os_scrape/supply_data.json — total_supply, max_supply, mint_status."""
    path = BASE / "data" / "os_scrape" / "supply_data.json"
    if not path.exists():
        return {}
    return json.load(open(path))

# ─── Parse trait data ────────────────────────────────────────────────────────

def parse_trait_data():
    """Load os_scrape/trait_data.json — avg_traits, nft_type, uniqueness_ratio."""
    path = BASE / "data" / "os_scrape" / "trait_data.json"
    if not path.exists():
        return {}
    return json.load(open(path))

# ─── Parse A3AC (awesome-3D-avatar-collections) ──────────────────────────────

def parse_a3ac():
    """Parse os_scrape/a3ac_parsed.json for 3D avatar collections from the A3AC registry."""
    path = BASE / "data" / "os_scrape" / "a3ac_parsed.json"
    if not path.exists():
        return []
    return json.load(open(path))

# ─── Parse research candidates ───────────────────────────────────────────────

def parse_research_candidates():
    """Parse os_scrape/research_candidates.json for 3D avatar collections found via deep research."""
    path = BASE / "data" / "os_scrape" / "research_candidates.json"
    if not path.exists():
        return []
    return json.load(open(path))

# ─── Build DB ────────────────────────────────────────────────────────────────

def build_db():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Parse all sources
    md_collections = parse_markdown()
    toxsam_projects, toxsam_avatars = parse_toxsam()
    os_candidates = parse_opensea()
    url_status = parse_url_status()
    collection_details = parse_collection_details()
    social_links, discord_status = parse_social_links()
    preview_images = parse_preview_images()
    collection_meta = parse_collection_meta()
    # Build a name→meta lookup for collections whose slugs don't match
    meta_by_name = {}
    for _slug, _entry in collection_meta.items():
        _f = _entry.get('fields', {})
        _name = (_f.get('name') or _slug).lower().strip()
        if _name:
            meta_by_name[_name] = _entry
    # Also build contract-prefix → meta lookup
    meta_by_contract = {}
    for _slug, _entry in collection_meta.items():
        _rs = _entry.get('resolved_slug', '')
        if _rs:
            meta_by_contract[_rs] = _entry
    supply_data = parse_supply_data()
    trait_data = parse_trait_data()

    # Enrich candidates with URL status + release dates + social from OpenSea
    for c in os_candidates:
        us = url_status.get(c['slug'])
        if us:
            c['url_status'] = us.get('status', '')
            c['wayback_available'] = 1 if us.get('wayback_available') else 0
            c['wayback_snapshots'] = us.get('wayback_snapshots', 0)
            c['wayback_url'] = us.get('wayback_cdx_url', '') or us.get('wayback_url', '')
        cd = collection_details.get(c['slug'])
        if cd:
            c['release_date'] = cd.get('created_date', '')[:10] if cd.get('created_date') else None
            contracts = cd.get('contracts', [])
            if contracts:
                c['contract'] = contracts[0]['address']
                c['chain'] = contracts[0]['chain']
        sl = social_links.get(c['slug'])
        if sl:
            c['discord_url'] = sl.get('discord_url', '')
            c['twitter_username'] = sl.get('twitter_username', '')
        ds = discord_status.get(c['slug'])
        if ds:
            c['discord_status'] = ds.get('status', '')
            c['discord_members'] = ds.get('member_count', 0)
        pi = preview_images.get(c['slug'])
        if pi:
            c['image_url'] = _img(pi.get('collection_image', ''))
            c['banner_image_url'] = _img(pi.get('banner_image', ''))
            c['sample_nft_image'] = pi.get('sample_nft_image', '')
            c['sample_nft_name'] = pi.get('sample_nft_name', '')
            if pi.get('vrm_url_https'):
                c['vrm_url_https'] = pi['vrm_url_https']
        # Collection meta (OpenSea API sweep: descriptions, num_owners, floor_price, etc.)
        cm = collection_meta.get(c.get('slug', ''))
        if not cm and c.get('opensea_slug'):
            cm = collection_meta.get(c['opensea_slug'])
        if not cm:
            # Try by exact name match
            cname = c.get('name', '').lower().strip()
            cm = meta_by_name.get(cname)
        if not cm:
            # Try partial name match
            cname = c.get('name', '').lower().strip()
            for _key, _entry in meta_by_name.items():
                if cname and (_key in cname or cname in _key):
                    cm = _entry
                    break
        if cm:
            f = cm.get('fields', {})
            if f.get('description') and not c.get('description'):
                c['description'] = f['description']
            if f.get('category'): c['category'] = f['category']
            if f.get('safelist_status'): c['safelist_status'] = f['safelist_status']
            if f.get('owner_address'): c['owner_address'] = f['owner_address']
            if f.get('royalty_fee'): c['royalty_fee'] = f['royalty_fee']
            if f.get('royalty_recipient'): c['royalty_recipient'] = f['royalty_recipient']
            if f.get('release_date') and not c.get('release_date'):
                c['release_date'] = f['release_date'][:10] if f['release_date'] else ''
            if f.get('instagram_username'): c['instagram_username'] = f['instagram_username']
            if f.get('telegram_url'): c['telegram_url'] = f['telegram_url']
            if f.get('is_nsfw') is not None: c['is_nsfw'] = f['is_nsfw']
            if f.get('rarity_strategy'): c['rarity_strategy'] = f['rarity_strategy']
            if f.get('num_owners'): c['num_owners'] = f['num_owners']
            if f.get('floor_price'): c['floor_price'] = f['floor_price']
            if f.get('floor_price_symbol'): c['floor_price_symbol'] = f['floor_price_symbol']
            if f.get('total_volume'): c['total_volume'] = f['total_volume']
            if f.get('total_sales'): c['total_sales'] = f['total_sales']
            if f.get('unique_item_count'): c['unique_item_count'] = f['unique_item_count']
            if f.get('one_day_volume'): c['one_day_volume'] = f['one_day_volume']
            if f.get('one_day_sales'): c['one_day_sales'] = f['one_day_sales']
            if f.get('seven_day_volume'): c['seven_day_volume'] = f['seven_day_volume']
            if f.get('seven_day_sales'): c['seven_day_sales'] = f['seven_day_sales']
            if f.get('thirty_day_volume'): c['thirty_day_volume'] = f['thirty_day_volume']
            if f.get('thirty_day_sales'): c['thirty_day_sales'] = f['thirty_day_sales']
            # Save resolved slug
            rs = cm.get('resolved_slug', '')
            if rs and rs != c.get('opensea_slug'):
                c['opensea_slug'] = rs
        sd = supply_data.get(c['slug'])
        if sd:
            c['total_supply'] = sd.get('total_supply')
            c['max_supply'] = sd.get('max_supply')
            c['mint_status'] = sd.get('mint_status', 'unknown')
            c['mint_progress'] = sd.get('mint_progress')
            c['max_supply_source'] = sd.get('max_supply_source', '')
        td = trait_data.get(c['slug'])
        if td:
            c['avg_traits'] = td.get('avg_traits')
            c['trait_types_count'] = td.get('trait_types')
            c['nft_type'] = td.get('nft_type', 'unknown')
            c['uniqueness_ratio'] = td.get('uniqueness_ratio')
            c['trait_type_names'] = td.get('trait_type_names', [])

    # Enrich collections with URL status + release dates + contracts from OpenSea
    all_contracts = []  # (collection_id, address, chain, is_primary)
    # Build a name→slug map from collection_details for fuzzy matching
    cd_names = {v.get('name', '').lower(): k for k, v in collection_details.items() if v.get('name')}
    for c in md_collections:
        # Try matching by opensea_slug, then by id (if it looks like a slug), then by name
        slug = c.get('opensea_slug') or (c['id'] if c['id'] in collection_details else None)
        if not slug:
            # Try name match
            slug = cd_names.get(c['name'].lower())
        if slug:
            us = url_status.get(slug)
            if us:
                c['url_status'] = us.get('status', '')
                c['wayback_available'] = 1 if us.get('wayback_available') else 0
                c['wayback_snapshots'] = us.get('wayback_snapshots', 0)
                c['wayback_url'] = us.get('wayback_cdx_url', '') or us.get('wayback_url', '')
            # Release date + contracts from OpenSea
            cd = collection_details.get(slug)
            if cd:
                c['release_date'] = cd.get('created_date', '')[:10] if cd.get('created_date') else None
                if not c.get('opensea_slug'):
                    c['opensea_slug'] = slug
                contracts = cd.get('contracts', [])
                if contracts:
                    # Set primary contract from OpenSea (may override markdown value)
                    primary = contracts[0]
                    c['contract'] = primary['address']
                    c['chain'] = primary['chain']
                    # If multiple contracts across chains, mark as multi
                    chains = set(ct['chain'] for ct in contracts)
                    if len(chains) > 1:
                        c['chain'] = 'multi'
                    # Collect all contracts for the contracts table
                    for i, ct in enumerate(contracts):
                        all_contracts.append({
                            'collection_id': c['id'],
                            'address': ct['address'],
                            'chain': ct['chain'],
                            'is_primary': 1 if i == 0 else 0,
                        })
            # Social links + Discord status
            sl = social_links.get(slug)
            if sl:
                c['discord_url'] = sl.get('discord_url', '')
                c['twitter_username'] = sl.get('twitter_username', '')
            ds = discord_status.get(slug)
            if ds:
                c['discord_status'] = ds.get('status', '')
                c['discord_members'] = ds.get('member_count', 0)
            # Preview images
            pi = preview_images.get(slug)
            if pi:
                c['image_url'] = _img(pi.get('collection_image', ''))
                c['banner_image_url'] = _img(pi.get('banner_image', ''))
                c['sample_nft_image'] = pi.get('sample_nft_image', '')
                c['sample_nft_name'] = pi.get('sample_nft_name', '')
                if pi.get('vrm_url_https'):
                    c['vrm_url_https'] = pi['vrm_url_https']
            # Supply data
            sd = supply_data.get(slug)
            if sd:
                c['total_supply'] = sd.get('total_supply')
                c['max_supply'] = sd.get('max_supply')
                c['mint_status'] = sd.get('mint_status', 'unknown')
                c['mint_progress'] = sd.get('mint_progress')
                c['max_supply_source'] = sd.get('max_supply_source', '')
            # Trait data
            td = trait_data.get(slug)
            if td:
                c['avg_traits'] = td.get('avg_traits')
                c['trait_types_count'] = td.get('trait_types')
                c['nft_type'] = td.get('nft_type', 'unknown')
                c['uniqueness_ratio'] = td.get('uniqueness_ratio')
                c['trait_type_names'] = td.get('trait_type_names', [])

        # Collection meta (OpenSea API sweep) — always try, even without slug
        cm = collection_meta.get(c.get('opensea_slug', ''))
        if not cm:
            cname = c.get('name', '').lower().strip()
            cm = meta_by_name.get(cname)
        if not cm and cname:
            for _key, _entry in meta_by_name.items():
                if cname and (_key in cname or cname in _key):
                    cm = _entry
                    break
        if cm:
            f = cm.get('fields', {})
            if f.get('description') and not c.get('description'):
                c['description'] = f['description']
            if f.get('category'): c['category'] = f['category']
            if f.get('safelist_status'): c['safelist_status'] = f['safelist_status']
            if f.get('owner_address'): c['owner_address'] = f['owner_address']
            if f.get('royalty_fee'): c['royalty_fee'] = f['royalty_fee']
            if f.get('royalty_recipient'): c['royalty_recipient'] = f['royalty_recipient']
            if f.get('release_date') and not c.get('release_date'):
                c['release_date'] = f['release_date'][:10] if f['release_date'] else ''
            if f.get('instagram_username'): c['instagram_username'] = f['instagram_username']
            if f.get('telegram_url'): c['telegram_url'] = f['telegram_url']
            if f.get('is_nsfw') is not None: c['is_nsfw'] = f['is_nsfw']
            if f.get('rarity_strategy'): c['rarity_strategy'] = f['rarity_strategy']
            if f.get('num_owners'): c['num_owners'] = f['num_owners']
            if f.get('floor_price'): c['floor_price'] = f['floor_price']
            if f.get('floor_price_symbol'): c['floor_price_symbol'] = f['floor_price_symbol']
            if f.get('total_volume'): c['total_volume'] = f['total_volume']
            if f.get('total_sales'): c['total_sales'] = f['total_sales']
            if f.get('unique_item_count'): c['unique_item_count'] = f['unique_item_count']
            if f.get('one_day_volume'): c['one_day_volume'] = f['one_day_volume']
            if f.get('one_day_sales'): c['one_day_sales'] = f['one_day_sales']
            if f.get('seven_day_volume'): c['seven_day_volume'] = f['seven_day_volume']
            if f.get('seven_day_sales'): c['seven_day_sales'] = f['seven_day_sales']
            if f.get('thirty_day_volume'): c['thirty_day_volume'] = f['thirty_day_volume']
            if f.get('thirty_day_sales'): c['thirty_day_sales'] = f['thirty_day_sales']
            # Don't overwrite image_url — preview_images already set it
            if f.get('image_url') and not c.get('image_url'):
                c['image_url'] = _img(f['image_url'])
            if f.get('banner_image_url') and not c.get('banner_image_url'):
                c['banner_image_url'] = _img(f['banner_image_url'])
            if f.get('project_url') and not c.get('project_url'):
                c['project_url'] = f['project_url']
            if f.get('discord_url') and not c.get('discord_url'):
                c['discord_url'] = f['discord_url']
            if f.get('twitter_username') and not c.get('twitter_username'):
                c['twitter_username'] = f['twitter_username']
            rs = cm.get('resolved_slug', '')
            if rs and not c.get('opensea_slug'):
                c['opensea_slug'] = rs

        # Fallback: try contract-based keys for collections without slug match
        if not slug and c.get('contract') and len(c['contract']) >= 20:
            contract_key = f"contract:{c['contract'][:10]}"
            pi = preview_images.get(contract_key)
            if pi:
                if not c.get('image_url'): c['image_url'] = _img(pi.get('collection_image', ''))
                if not c.get('banner_image_url'): c['banner_image_url'] = _img(pi.get('banner_image', ''))
                if not c.get('sample_nft_image'): c['sample_nft_image'] = pi.get('sample_nft_image', '')
                if not c.get('sample_nft_name'): c['sample_nft_name'] = pi.get('sample_nft_name', '')
                if not c.get('vrm_url_https') and pi.get('vrm_url_https'):
                    c['vrm_url_https'] = pi['vrm_url_https']
                # Use resolved slug for meta lookup
                rs = pi.get('resolved_slug', '')
                if rs:
                    c['opensea_slug'] = rs
                    cm = collection_meta.get(rs)
                    if cm:
                        f = cm.get('fields', {})
                        if f.get('description') and not c.get('description'):
                            c['description'] = f['description']
                        if f.get('num_owners'): c['num_owners'] = f['num_owners']
                        if f.get('floor_price'): c['floor_price'] = f['floor_price']
                        if f.get('floor_price_symbol'): c['floor_price_symbol'] = f['floor_price_symbol']
                        if f.get('total_volume'): c['total_volume'] = f['total_volume']
                        if f.get('total_sales'): c['total_sales'] = f['total_sales']
                        if f.get('category'): c['category'] = f['category']
                        if f.get('safelist_status'): c['safelist_status'] = f['safelist_status']
                        if f.get('owner_address'): c['owner_address'] = f['owner_address']
                        if f.get('royalty_fee'): c['royalty_fee'] = f['royalty_fee']
                        if f.get('royalty_recipient'): c['royalty_recipient'] = f['royalty_recipient']
                        if f.get('release_date') and not c.get('release_date'):
                            c['release_date'] = f['release_date'][:10] if f['release_date'] else ''
                        if f.get('instagram_username'): c['instagram_username'] = f['instagram_username']
                        if f.get('telegram_url'): c['telegram_url'] = f['telegram_url']
                        if f.get('is_nsfw') is not None: c['is_nsfw'] = f['is_nsfw']
                        if f.get('rarity_strategy'): c['rarity_strategy'] = f['rarity_strategy']
                        if f.get('unique_item_count'): c['unique_item_count'] = f['unique_item_count']
                        if f.get('one_day_volume'): c['one_day_volume'] = f['one_day_volume']
                        if f.get('one_day_sales'): c['one_day_sales'] = f['one_day_sales']
                        if f.get('seven_day_volume'): c['seven_day_volume'] = f['seven_day_volume']
                        if f.get('seven_day_sales'): c['seven_day_sales'] = f['seven_day_sales']
                        if f.get('thirty_day_volume'): c['thirty_day_volume'] = f['thirty_day_volume']
                        if f.get('thirty_day_sales'): c['thirty_day_sales'] = f['thirty_day_sales']
            sd = supply_data.get(contract_key)
            if sd:
                SHARED_STORE = '0x495f947276749ce646f68ac8c248420045cb7b5e'
                is_shared = c.get('contract', '').lower().startswith(SHARED_STORE)
                if not is_shared:
                    c['total_supply'] = sd.get('total_supply')
                    c['max_supply'] = sd.get('max_supply')
                    c['mint_status'] = sd.get('mint_status', 'unknown')
                    c['mint_progress'] = sd.get('mint_progress')
                    c['max_supply_source'] = sd.get('max_supply_source', '')
            td = trait_data.get(contract_key)
            if td:
                c['avg_traits'] = td.get('avg_traits')
                c['trait_types_count'] = td.get('trait_types')
                c['nft_type'] = td.get('nft_type', 'unknown')
                c['uniqueness_ratio'] = td.get('uniqueness_ratio')
                c['trait_type_names'] = td.get('trait_type_names', [])
            sl = social_links.get(contract_key)
            if sl:
                c['discord_url'] = sl.get('discord_url', '')
                c['twitter_username'] = sl.get('twitter_username', '')
            ds = discord_status.get(contract_key)
            if ds:
                c['discord_status'] = ds.get('status', '')
                c['discord_members'] = ds.get('member_count', 0)

    # Insert ToxSam projects as collections
    for p in toxsam_projects:
        pid = p['id']
        # Check if already in md_collections by slugified name
        existing = next((c for c in md_collections if c['id'] == pid or slugify(c['name']) == pid), None)
        if existing:
            existing['license'] = p.get('license', '')
            existing['creator'] = p.get('creator_id', '')
            existing['description'] = p.get('description', '')
            existing['source'] = 'toxsam+curated'
            # Normalize avatar collection_id to match the existing collection's id
            if existing['id'] != pid:
                for a in toxsam_avatars:
                    if a['collection_id'] == pid:
                        a['collection_id'] = existing['id']
            # Count avatars
            af = [a for a in toxsam_avatars if a['collection_id'] == existing['id']]
            existing['avatar_count'] = len(af)
        else:
            md_collections.append({
                'id': pid,
                'name': p['name'],
                'tier': 'arweave' if p.get('storage_type') == 'arweave' else 'A',
                'chain': 'arweave' if p.get('storage_type') == 'arweave' else 'ethereum',
                'contract': None,
                'opensea_slug': None,
                'vrm_param': None,
                'vrm_url_pattern': None,
                'license_category': 'green' if p.get('license') == 'CC0' else 'yellow' if p.get('license') == 'CC-BY' else 'unknown',
                'vrm_license': p.get('license', ''),
                'commercial_use': 'Allow' if p.get('license') in ('CC0', 'CC-BY') else 'unknown',
                'allowed_user': 'Everyone' if p.get('license') == 'CC0' else 'unknown',
                'avatar_count': sum(1 for a in toxsam_avatars if a['collection_id'] == pid),
                'creator': p.get('creator_id', ''),
                'description': p.get('description', ''),
                'notes': '',
                'source': 'toxsam',
            })

    # Add A3AC (awesome-3D-avatar-collections) entries
    a3ac_entries = parse_a3ac()
    # Build set of existing contracts for dedup
    existing_contracts = set()
    for c in md_collections:
        if c.get('contract') and len(c['contract']) >= 20:
            existing_contracts.add(c['contract'].lower())
    # Also check by name (fuzzy)
    existing_names = set()
    for c in md_collections:
        existing_names.add(c['name'].lower())

    for e in a3ac_entries:
        if not e.get('contract') or not e.get('name', '').strip():
            continue
        contract_lower = e['contract'].lower()
        name_lower = e['name'].lower()
        # Normalize names for matching (strip punctuation/parens)
        def norm_name(s):
            import re as _re
            return set(_re.sub(r'[^a-z0-9\s]', ' ', s.lower()).split())
        name_words = norm_name(e['name'])
        # Skip if we already have this contract (but not for shared store contracts)
        SHARED_STORE_CONTRACTS = {'0x495f947276749ce646f68ac8c248420045cb7b5e'}
        if contract_lower in existing_contracts and contract_lower not in SHARED_STORE_CONTRACTS:
            # But update project_url and preview image if missing
            for c in md_collections:
                if (c.get('contract') or '').lower() == contract_lower:
                    if not c.get('project_url') and e.get('project_url'):
                        c['project_url'] = e['project_url']
                    if False:  # A3AC preview URLs are stale, use OpenSea API instead
                        c['image_url'] = e['preview_image']
                    if not c.get('sample_metadata_url') and e.get('metadata_url'):
                        c['sample_metadata_url'] = e['metadata_url']
                    break
            continue

        # For shared store contracts, also check name match before enriching
        if contract_lower in SHARED_STORE_CONTRACTS:
            # Try to find a name match among collections with this contract
            name_match_found = False
            for c in md_collections:
                if (c.get('contract') or '').lower() == contract_lower:
                    cn = norm_name(c['name'])
                    if cn & name_words:  # at least one word in common
                        if not c.get('project_url') and e.get('project_url'):
                            c['project_url'] = e['project_url']
                        if False:  # A3AC preview URLs are stale, use OpenSea API instead
                            c['image_url'] = e['preview_image']
                        if not c.get('sample_metadata_url') and e.get('metadata_url'):
                            c['sample_metadata_url'] = e['metadata_url']
                        if not c.get('vrm_param') and e.get('vrm_param'):
                            c['vrm_param'] = e['vrm_param']
                        name_match_found = True
                        break
            if name_match_found:
                continue

        # Check name overlap to avoid duplicates
        is_dup = False
        for existing_name in existing_names:
            # Exact name match
            if name_lower == existing_name:
                is_dup = True
                break
            existing_words = norm_name(existing_name)
            overlap = name_words & existing_words
            # Match if 2+ word overlap, or 1 word overlap and one is subset of other
            if len(overlap) >= 2:
                is_dup = True
                break
            if len(overlap) == 1 and (overlap <= name_words or overlap <= existing_words):
                # Single significant word in common (e.g. "PixelBeasts" vs "PixelBeasts (Beastopia)")
                # Only count as dup if the overlapping word is > 4 chars (avoid "the", "of", etc.)
                w = next(iter(overlap))
                if len(w) > 4:
                    is_dup = True
                    break

        if is_dup:
            # Still enrich the existing collection with A3AC data
            for c in md_collections:
                cn = norm_name(c['name'])
                overlap = cn & name_words
                if cn == name_words or len(overlap) >= 2 or (len(overlap) == 1 and len(next(iter(overlap))) > 4 and (overlap <= cn or overlap <= name_words)):
                    if not c.get('project_url') and e.get('project_url'):
                        c['project_url'] = e['project_url']
                    if False:  # A3AC preview URLs are stale, use OpenSea API instead
                        c['image_url'] = e['preview_image']
                    if not c.get('sample_metadata_url') and e.get('metadata_url'):
                        c['sample_metadata_url'] = e['metadata_url']
                    if not c.get('vrm_param') and e.get('vrm_param'):
                        c['vrm_param'] = e['vrm_param']
                    break
            continue

        # Add as new collection
        cid = f"a3ac-{e['contract'][:8]}"
        md_collections.append({
            'id': cid,
            'name': e['name'],
            'tier': 'C',  # 3D but not VRM (or VRM if has_vrm)
            'chain': 'ethereum',
            'contract': e['contract'],
            'opensea_slug': None,
            'vrm_param': e.get('vrm_param', ''),
            'vrm_url_pattern': None,
            'license_category': 'unknown',
            'vrm_license': '',
            'commercial_use': 'unknown',
            'allowed_user': 'unknown',
            'avatar_count': None,
            'creator': e['name'],
            'description': '',
            'notes': f"From A3AC registry. VRM: {'Yes' if e.get('has_vrm') else 'No'}. Param: {e.get('param_raw','')}",
            'source': 'a3ac-registry',
            'project_url': e.get('project_url', ''),
            'image_url': '',  # Will be filled from OpenSea API, not A3AC (stale URLs)
            'sample_metadata_url': e.get('metadata_url', ''),
        })
        existing_contracts.add(contract_lower)
        existing_names.add(name_lower)

    # Add research candidates (from deep research — other marketplaces/chains)
    research_entries = parse_research_candidates()
    for e in research_entries:
        if not e.get('contract') or not e.get('name', '').strip():
            continue
        contract_lower = e['contract'].lower()
        if contract_lower in existing_contracts:
            continue  # Already have this collection
        name_lower = e['name'].lower()
        if name_lower in existing_names:
            continue
        cid = f"research-{e['contract'][:8]}"
        md_collections.append({
            'id': cid,
            'name': e['name'],
            'tier': e.get('tier', 'C'),
            'chain': e.get('chain', 'ethereum'),
            'contract': e['contract'],
            'opensea_slug': None,
            'vrm_param': None,
            'vrm_url_pattern': None,
            'license_category': 'unknown',
            'vrm_license': '',
            'commercial_use': 'unknown',
            'allowed_user': 'unknown',
            'avatar_count': None,
            'creator': '',
            'description': e.get('notes', ''),
            'notes': e.get('notes', ''),
            'source': e.get('source', 'research'),
            'project_url': e.get('url', ''),
            'image_url': '',
            'sample_metadata_url': '',
        })
        existing_contracts.add(contract_lower)
        existing_names.add(name_lower)

    # Second enrichment pass: enrich collections that weren't fully enriched in the first pass
    for c in md_collections:
        # Only process collections with contracts
        if not c.get('contract') or len(c['contract']) < 20:
            continue
        # Skip if already has supply + traits + release_date from first pass
        if c.get('total_supply') is not None and c.get('nft_type') and c.get('release_date'):
            continue
        # Use contract-based keys for collections that still have missing data
        if c.get('contract') and len(c['contract']) >= 20:
            contract_key = f"contract:{c['contract'][:10]}"
            pi = preview_images.get(contract_key)
            if pi:
                if not c.get('image_url'): c['image_url'] = _img(pi.get('collection_image', ''))
                if not c.get('banner_image_url'): c['banner_image_url'] = _img(pi.get('banner_image', ''))
                if not c.get('sample_nft_image'): c['sample_nft_image'] = pi.get('sample_nft_image', '')
                if not c.get('sample_nft_name'): c['sample_nft_name'] = pi.get('sample_nft_name', '')
                if not c.get('vrm_url_https') and pi.get('vrm_url_https'):
                    c['vrm_url_https'] = pi['vrm_url_https']
            sd = supply_data.get(contract_key)
            if sd:
                # Skip slug resolution for shared store contracts (multiple collections share one contract)
                SHARED_STORE = '0x495f947276749ce646f68ac8c248420045cb7b5e'
                is_shared = c.get('contract', '').lower().startswith(SHARED_STORE)
                if not is_shared:
                    c['total_supply'] = sd.get('total_supply')
                    c['max_supply'] = sd.get('max_supply')
                    c['mint_status'] = sd.get('mint_status', 'unknown')
                    c['mint_progress'] = sd.get('mint_progress')
                    c['max_supply_source'] = sd.get('max_supply_source', '')
                    # Use resolved slug to get release_date, description, etc.
                    resolved = sd.get('_resolved_slug')
                    if resolved:
                        if not c.get('opensea_slug'):
                            c['opensea_slug'] = resolved
                        cd = collection_details.get(resolved)
                        if cd:
                            if not c.get('release_date') and cd.get('created_date'):
                                c['release_date'] = cd['created_date'][:10]
                            if not c.get('description') and cd.get('description'):
                                c['description'] = cd['description']
                            if not c.get('image_url') and cd.get('image_url'):
                                c['image_url'] = _img(cd['image_url'])
                            if not c.get('banner_image_url') and cd.get('banner_image_url'):
                                c['banner_image_url'] = _img(cd['banner_image_url'])
                            if not c.get('discord_url') and cd.get('discord_url'):
                                c['discord_url'] = cd['discord_url']
                            if not c.get('twitter_username') and cd.get('twitter_username'):
                                c['twitter_username'] = cd['twitter_username']
            td = trait_data.get(contract_key)
            if td:
                c['avg_traits'] = td.get('avg_traits')
                c['trait_types_count'] = td.get('trait_types')
                c['nft_type'] = td.get('nft_type', 'unknown')
                c['uniqueness_ratio'] = td.get('uniqueness_ratio')
                c['trait_type_names'] = td.get('trait_type_names', [])
            sl = social_links.get(contract_key)
            if sl:
                c['discord_url'] = sl.get('discord_url', '')
                c['twitter_username'] = sl.get('twitter_username', '')
            ds = discord_status.get(contract_key)
            if ds:
                c['discord_status'] = ds.get('status', '')
                c['discord_members'] = ds.get('member_count', 0)
            # Collection meta from OpenSea API sweep
            resolved_slug = c.get('opensea_slug', '')
            if resolved_slug:
                cm = collection_meta.get(resolved_slug)
                if cm:
                    f = cm.get('fields', {})
                    if f.get('description') and not c.get('description'):
                        c['description'] = f['description']
                    if f.get('num_owners'): c['num_owners'] = f['num_owners']
                    if f.get('floor_price'): c['floor_price'] = f['floor_price']
                    if f.get('floor_price_symbol'): c['floor_price_symbol'] = f['floor_price_symbol']
                    if f.get('total_volume'): c['total_volume'] = f['total_volume']
                    if f.get('total_sales'): c['total_sales'] = f['total_sales']
                    if f.get('category'): c['category'] = f['category']
                    if f.get('safelist_status'): c['safelist_status'] = f['safelist_status']
                    if f.get('owner_address'): c['owner_address'] = f['owner_address']
                    if f.get('royalty_fee'): c['royalty_fee'] = f['royalty_fee']
                    if f.get('royalty_recipient'): c['royalty_recipient'] = f['royalty_recipient']
                    if f.get('release_date') and not c.get('release_date'):
                        c['release_date'] = f['release_date'][:10] if f['release_date'] else ''
                    if f.get('instagram_username'): c['instagram_username'] = f['instagram_username']
                    if f.get('telegram_url'): c['telegram_url'] = f['telegram_url']
                    if f.get('is_nsfw') is not None: c['is_nsfw'] = f['is_nsfw']
                    if f.get('rarity_strategy'): c['rarity_strategy'] = f['rarity_strategy']
                    if f.get('unique_item_count'): c['unique_item_count'] = f['unique_item_count']
                    if f.get('one_day_volume'): c['one_day_volume'] = f['one_day_volume']
                    if f.get('one_day_sales'): c['one_day_sales'] = f['one_day_sales']
                    if f.get('seven_day_volume'): c['seven_day_volume'] = f['seven_day_volume']
                    if f.get('seven_day_sales'): c['seven_day_sales'] = f['seven_day_sales']
                    if f.get('thirty_day_volume'): c['thirty_day_volume'] = f['thirty_day_volume']
                    if f.get('thirty_day_sales'): c['thirty_day_sales'] = f['thirty_day_sales']

    # Deduplicate collections by id (merge)
    seen = {}
    for c in md_collections:
        cid = c['id']
        if cid in seen:
            # Merge: prefer non-null values
            for k, v in c.items():
                if v and not seen[cid].get(k):
                    seen[cid][k] = v
        else:
            seen[cid] = c
    md_collections = list(seen.values())
    # Filter out entries with empty names
    md_collections = [c for c in md_collections if c.get('name', '').strip()]
    # Assign Tier B to any collections without a tier
    for c in md_collections:
        if not c.get('tier') or c.get('tier') == 'unknown':
            c['tier'] = 'B'

    # Insert collections
    for c in md_collections:
        conn.execute("""
            INSERT OR REPLACE INTO collections
            (id, name, tier, chain, contract, opensea_slug, release_date,
             vrm_param, vrm_url_pattern,
             license_category, vrm_license, commercial_use, allowed_user, redistribution,
             avatar_count, creator, description, notes, source,
             url_status, wayback_available, wayback_snapshots, wayback_url,
             discord_url, discord_status, discord_members, twitter_username,
             image_url, banner_image_url, sample_nft_image, sample_nft_name, vrm_url_https,
             total_supply, max_supply, mint_status, mint_progress, max_supply_source,
             avg_traits, trait_types_count, nft_type, uniqueness_ratio, trait_type_names,
             project_url, sample_metadata_url,
             num_owners, floor_price, floor_price_symbol, total_volume, total_sales,
             category, safelist_status, owner_address, royalty_fee, royalty_recipient,
             instagram_username, telegram_url, is_nsfw, rarity_strategy, unique_item_count,
             one_day_volume, one_day_sales, seven_day_volume, seven_day_sales,
             thirty_day_volume, thirty_day_sales)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            c['id'], c['name'], c.get('tier'), c.get('chain'), c.get('contract'),
            c.get('opensea_slug'), c.get('release_date'),
            c.get('vrm_param'), c.get('vrm_url_pattern'),
            c.get('license_category', 'unknown'), c.get('vrm_license', ''),
            c.get('commercial_use', 'unknown'), c.get('allowed_user', 'unknown'),
            c.get('redistribution', 'unknown'),
            c.get('avatar_count'), c.get('creator', ''), c.get('description', ''),
            c.get('notes', ''), c.get('source', ''),
            c.get('url_status', ''), c.get('wayback_available', 0),
            c.get('wayback_snapshots', 0), c.get('wayback_url', ''),
            c.get('discord_url', ''), c.get('discord_status', ''),
            c.get('discord_members', 0), c.get('twitter_username', ''),
            c.get('image_url', ''), c.get('banner_image_url', ''),
            c.get('sample_nft_image', ''), c.get('sample_nft_name', ''),
            c.get('vrm_url_https', ''),
            c.get('total_supply'), c.get('max_supply'),
            c.get('mint_status', 'unknown'), c.get('mint_progress'),
            c.get('max_supply_source', ''),
            c.get('avg_traits'), c.get('trait_types_count'),
            c.get('nft_type', 'unknown'), c.get('uniqueness_ratio'),
            json.dumps(c.get('trait_type_names', [])),
            c.get('project_url', ''), c.get('sample_metadata_url', ''),
            c.get('num_owners'), c.get('floor_price'), c.get('floor_price_symbol'),
            c.get('total_volume'), c.get('total_sales'),
            c.get('category', ''), c.get('safelist_status', ''),
            c.get('owner_address', ''), c.get('royalty_fee'),
            c.get('royalty_recipient', ''),
            c.get('instagram_username', ''), c.get('telegram_url', ''),
            c.get('is_nsfw', 0), c.get('rarity_strategy', ''),
            c.get('unique_item_count'),
            c.get('one_day_volume'), c.get('one_day_sales'),
            c.get('seven_day_volume'), c.get('seven_day_sales'),
            c.get('thirty_day_volume'), c.get('thirty_day_sales'),
        ))

    # Insert all contracts (multi-chain collections)
    for ct in all_contracts:
        conn.execute("""
            INSERT OR REPLACE INTO contracts (collection_id, address, chain, is_primary)
            VALUES (?,?,?,?)
        """, (ct['collection_id'], ct['address'], ct['chain'], ct['is_primary']))

    # Also add contracts from markdown for collections without OpenSea data
    for c in md_collections:
        if c.get('contract') and not any(ct['collection_id'] == c['id'] for ct in all_contracts):
            conn.execute("""
                INSERT OR REPLACE INTO contracts (collection_id, address, chain, is_primary)
                VALUES (?,?,?,1)
            """, (c['id'], c['contract'], c.get('chain', 'ethereum')))

    # Insert avatars
    for a in toxsam_avatars:
        conn.execute("""
            INSERT OR REPLACE INTO avatars
            (id, collection_id, name, description, model_file_url, format, thumbnail_url, is_public, metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            a['id'], a['collection_id'], a['name'], a['description'],
            a['model_file_url'], a['format'], a['thumbnail_url'], a['is_public'],
            a['metadata_json'],
        ))

    # Insert OpenSea candidates
    for c in os_candidates:
        conn.execute("""
            INSERT OR REPLACE INTO opensea_candidates
            (slug, name, chain, contract, release_date, status, vrm_param, vrm_url, sample_nft, metadata_url, source_query,
             url_status, wayback_available, wayback_snapshots, wayback_url,
             discord_url, discord_status, discord_members, twitter_username,
             image_url, banner_image_url, sample_nft_image, sample_nft_name, vrm_url_https,
             total_supply, max_supply, mint_status, mint_progress, max_supply_source,
             avg_traits, trait_types_count, nft_type, uniqueness_ratio, trait_type_names)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?)
        """, (
            c['slug'], c['name'], c.get('chain', 'ethereum'), c.get('contract'),
            c.get('release_date'),
            c.get('status', 'not_checked'), c.get('vrm_param', ''), c.get('vrm_url', ''),
            c.get('sample_nft', ''), c.get('metadata_url', ''), c.get('source_query', ''),
            c.get('url_status', ''), c.get('wayback_available', 0),
            c.get('wayback_snapshots', 0), c.get('wayback_url', ''),
            c.get('discord_url', ''), c.get('discord_status', ''),
            c.get('discord_members', 0), c.get('twitter_username', ''),
            c.get('image_url', ''), c.get('banner_image_url', ''),
            c.get('sample_nft_image', ''), c.get('sample_nft_name', ''),
            c.get('vrm_url_https', ''),
            c.get('total_supply'), c.get('max_supply'),
            c.get('mint_status', 'unknown'), c.get('mint_progress'),
            c.get('max_supply_source', ''),
            c.get('avg_traits'), c.get('trait_types_count'),
            c.get('nft_type', 'unknown'), c.get('uniqueness_ratio'),
            json.dumps(c.get('trait_type_names', [])),
        ))

    # Insert sources
    sources = [
        ('curated-registry', 'awesome-3D-avatar-collections', 'https://github.com/itsmetamike/awesome-3D-avatar-collections', 'registry'),
        ('toxsam-projects', 'ToxSam open-source-avatars', 'https://github.com/ToxSam/open-source-avatars', 'manifest'),
        ('opensea-api', 'OpenSea API v2', 'https://docs.opensea.io/', 'api'),
        ('hackmd-xr', 'NFT 3D Avatars catalog', 'https://hackmd.io/@XR/nftavatars', 'markdown'),
        ('vrm-spec', 'VRM specification', 'https://github.com/vrm-c/vrm-specification', 'spec'),
    ]
    for s in sources:
        conn.execute("INSERT OR REPLACE INTO sources VALUES (?,?,?,?)", s)

    conn.commit()

    # Stats
    stats = {
        'collections': conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0],
        'avatars': conn.execute("SELECT COUNT(*) FROM avatars").fetchone()[0],
        'opensea_candidates': conn.execute("SELECT COUNT(*) FROM opensea_candidates").fetchone()[0],
        'tier_a': conn.execute("SELECT COUNT(*) FROM collections WHERE tier='A'").fetchone()[0],
        'tier_b': conn.execute("SELECT COUNT(*) FROM collections WHERE tier='B'").fetchone()[0],
        'green': conn.execute("SELECT COUNT(*) FROM collections WHERE license_category='green'").fetchone()[0],
        'yellow': conn.execute("SELECT COUNT(*) FROM collections WHERE license_category='yellow'").fetchone()[0],
        'red': conn.execute("SELECT COUNT(*) FROM collections WHERE license_category='red'").fetchone()[0],
        'urls_alive': conn.execute("SELECT COUNT(*) FROM opensea_candidates WHERE url_status='alive'").fetchone()[0],
        'urls_dead': conn.execute("SELECT COUNT(*) FROM opensea_candidates WHERE url_status='dead'").fetchone()[0],
        'urls_error': conn.execute("SELECT COUNT(*) FROM opensea_candidates WHERE url_status='error' OR url_status IS NULL OR url_status=''").fetchone()[0],
        'wayback_archived': conn.execute("SELECT COUNT(*) FROM opensea_candidates WHERE wayback_available=1").fetchone()[0],
        'dc_alive': conn.execute("SELECT COUNT(*) FROM opensea_candidates WHERE discord_status='alive'").fetchone()[0],
        'dc_dead': conn.execute("SELECT COUNT(*) FROM opensea_candidates WHERE discord_status='dead'").fetchone()[0],
        'dc_members': conn.execute("SELECT COALESCE(SUM(discord_members),0) FROM opensea_candidates WHERE discord_status='alive'").fetchone()[0],
        'mint_capped': conn.execute("SELECT COUNT(*) FROM collections WHERE mint_status IN ('capped','likely_capped')").fetchone()[0],
        'mint_ongoing': conn.execute("SELECT COUNT(*) FROM collections WHERE mint_status='ongoing'").fetchone()[0],
    }
    conn.close()
    return stats

# ─── Build static HTML ───────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VRM NFT Collection Index</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Poppins:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --accent: #735FFA;
  --accent-dim: rgba(115, 95, 250, 0.15);
  --accent-glow: rgba(115, 95, 250, 0.4);
  --bg-base: #0D0D0F;
  --bg-raised: #141416;
  --bg-surface: #1A1D21;
  --bg-hover: #2D3039;
  --text-primary: #FFFFFF;
  --text-secondary: #A1A1AA;
  --text-muted: #71717A;
  --border-default: rgba(255, 255, 255, 0.06);
  --border-hover: rgba(255, 255, 255, 0.12);
  --success: #4CC38A;
  --warning: #E5B849;
  --error: #FF5A5A;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
       background: var(--bg-base); color: var(--text-secondary); line-height: 1.5; }
header { background: var(--bg-raised); border-bottom: 1px solid var(--border-default); padding: 16px 24px; position: sticky; top: 0; z-index: 100; }
h1 { font-family: 'Poppins', sans-serif; font-size: 20px; font-weight: 600; color: var(--text-primary); display: inline; }
h1 span { color: var(--accent); }
.stats { float: right; font-size: 13px; color: var(--text-muted); display: flex; gap: 16px; align-items: center; }
.stats span { display: flex; align-items: center; gap: 4px; }
.stats b { color: var(--text-primary); font-weight: 600; }
.controls { padding: 12px 24px; background: var(--bg-raised); border-bottom: 1px solid var(--border-default); display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
input[type=text] { width: 300px; max-width: 100%; padding: 8px 12px; background: var(--bg-surface); border: 1px solid var(--border-default);
                   border-radius: 8px; color: var(--text-primary); font-size: 14px; font-family: 'Inter', sans-serif;
                   transition: border-color 0.15s; }
input[type=text]:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim); }
select { padding: 6px 10px; background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: 8px;
         color: var(--text-secondary); font-size: 13px; font-family: 'Inter', sans-serif; margin-left: 4px;
         transition: border-color 0.15s; cursor: pointer; }
select:hover { border-color: var(--border-hover); }
select:focus { outline: none; border-color: var(--accent); }
label { font-size: 13px; color: var(--text-muted); font-weight: 500; margin-left: 8px; }
main { padding: 16px 24px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 10px 12px; background: var(--bg-raised); border-bottom: 1px solid var(--border-default);
     color: var(--text-muted); font-weight: 500; font-family: 'Inter', sans-serif; position: sticky; top: 100px; cursor: pointer; user-select: none;
     transition: color 0.15s; }
th:hover { color: var(--accent); }
td { padding: 10px 12px; border-bottom: 1px solid var(--border-default); vertical-align: top; }
tr { transition: background 0.1s; }
tr:hover { background: var(--bg-surface); }
.badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; font-family: 'Inter', sans-serif; }
.badge-green { background: rgba(76, 195, 138, 0.15); color: var(--success); }
.badge-yellow { background: rgba(229, 184, 73, 0.15); color: var(--warning); }
.badge-red { background: rgba(255, 90, 90, 0.15); color: var(--error); }
.badge-unknown { background: var(--bg-surface); color: var(--text-muted); }
.badge-tier-A { background: var(--accent-dim); color: var(--accent); }
.badge-tier-B { background: rgba(229, 184, 73, 0.12); color: var(--warning); }
.badge-tier-C { background: rgba(255, 90, 90, 0.12); color: var(--error); }
.badge-tier-arweave { background: rgba(115, 95, 250, 0.12); color: #a78bfa; }
.badge-tier-infra { background: rgba(76, 195, 138, 0.12); color: var(--success); }
.badge-tier-not_vrm { background: rgba(255, 90, 90, 0.12); color: var(--error); }
.mono { font-family: 'SF Mono', 'JetBrains Mono', Monaco, monospace; font-size: 12px; color: var(--text-muted); }
a { color: var(--accent); text-decoration: none; transition: opacity 0.15s; }
a:hover { opacity: 0.8; text-decoration: none; }
.url-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tab-bar { margin-bottom: 12px; display: flex; gap: 4px; }
.tab { display: inline-block; padding: 8px 18px; background: var(--bg-raised); border: 1px solid var(--border-default);
       border-radius: 8px; cursor: pointer; font-size: 13px; color: var(--text-muted); font-weight: 500;
       transition: all 0.15s; }
.tab:hover { background: var(--bg-surface); color: var(--text-secondary); }
.tab.active { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }
.count { color: var(--text-muted); font-size: 12px; }
.avatar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.avatar-card { background: var(--bg-raised); border: 1px solid var(--border-default); border-radius: 12px; padding: 12px; transition: border-color 0.15s; }
.avatar-card:hover { border-color: var(--border-hover); }
.avatar-card img { width: 100%; border-radius: 8px; margin-bottom: 8px; }
.avatar-card h4 { font-size: 13px; color: var(--text-primary); font-weight: 500; }
.avatar-card .mono { font-size: 11px; }
.avatar-card a { font-size: 11px; }
#avatarView { display: none; }
.empty { text-align: center; padding: 40px; color: var(--text-muted); }
.thumb { width: 48px; height: 48px; border-radius: 8px; object-fit: cover; vertical-align: middle; cursor: pointer; transition: outline 0.15s; }
.thumb:hover { outline: 2px solid var(--accent); }
.thumb-placeholder { display: inline-block; width: 48px; height: 48px; border-radius: 8px; background: var(--bg-surface); color: var(--text-muted); text-align: center; line-height: 48px; font-size: 20px; }
.desc-row td { padding: 2px 8px 8px 56px !important; font-size: 12px; color: var(--text-muted); border-top: none !important; line-height: 1.4; }
.desc-cell { max-width: 800px; }
/* Mobile responsive */
@media (max-width: 768px) {
  header { flex-direction: column; gap: 8px; }
  .controls { flex-direction: column; align-items: stretch; }
  .controls input[type="text"] { width: 100% !important; max-width: 100%; }
  .controls select { width: 100%; }
  #collectionsTable { font-size: 12px; display: block; overflow-x: auto; white-space: nowrap; }
  #collectionsTable thead, #collectionsTable tbody { display: table; width: max-content; }
  .avatar-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
  .thumb { width: 36px; height: 36px; }
  .thumb-placeholder { width: 36px; height: 36px; line-height: 36px; }
  .desc-row { display: none; }
}
/* VRM viewer modal */
#vrmModal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 1000; backdrop-filter: blur(4px); }
#vrmModal.active { display: flex; }
#vrmModalContent { background: var(--bg-raised); border: 1px solid var(--border-default); border-radius: 16px; margin: auto; width: 90%; max-width: 900px; max-height: 90vh; display: flex; flex-direction: column; box-shadow: 0 24px 80px rgba(0,0,0,0.5); }
#vrmModalHeader { padding: 16px 24px; border-bottom: 1px solid var(--border-default); display: flex; justify-content: space-between; align-items: center; }
#vrmModalHeader h3 { font-family: 'Poppins', sans-serif; font-size: 16px; font-weight: 600; color: var(--text-primary); }
#vrmModalClose { cursor: pointer; color: var(--text-muted); font-size: 24px; background: none; border: none; transition: color 0.15s; }
#vrmModalClose:hover { color: var(--error); }
#vrmCanvasContainer { flex: 1; min-height: 500px; position: relative; background: var(--bg-base); }
#vrmCanvas { width: 100%; height: 100%; display: block; }
#vrmLoading { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); color: var(--text-muted); font-size: 14px; display: none; }
#vrmLoading.active { display: block; }
#vrmError { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); color: var(--error); font-size: 14px; text-align: center; display: none; max-width: 400px; }
#vrmError.active { display: block; }
#vrmModalFooter { padding: 10px 24px; border-top: 1px solid var(--border-default); font-size: 12px; color: var(--text-muted); display: flex; gap: 16px; align-items: center; }
#vrmModalFooter a { color: var(--accent); }
/* Image preview modal */
#imgModal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; backdrop-filter: blur(4px); }
#imgModal.active { display: flex; align-items: center; justify-content: center; }
#imgModalContent { display: flex; flex-direction: column; align-items: center; gap: 16px; max-width: 95%; max-height: 90vh; }
#imgModalBanner { max-width: 800px; width: 100%; max-height: 200px; object-fit: cover; border-radius: 12px; border: 1px solid var(--border-default); }
#imgModalImg { max-width: 300px; max-height: 300px; border-radius: 12px; border: 1px solid var(--border-default); }
#imgModalLabel { font-family: 'Inter', sans-serif; font-size: 14px; color: var(--text-secondary); font-weight: 500; }
#imgModalClose { position: fixed; top: 20px; right: 30px; cursor: pointer; color: var(--text-primary); font-size: 28px; background: none; border: none; z-index: 1001; transition: color 0.15s; }
#imgModalClose:hover { color: var(--error); }
/* VRM button */
.vrm-btn { cursor: pointer; background: var(--accent-dim); color: var(--accent); border: 1px solid var(--border-default); border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 500; font-family: 'Inter', sans-serif; transition: all 0.15s; }
.vrm-btn:hover { background: var(--accent); color: var(--text-primary); border-color: var(--accent); }
/* Scrollbar */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: var(--bg-hover); border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
</style>
</head>
<body>
<header>
  <h1>VRM <span>Collection Index</span></h1>
  <div class="stats">
    <span>Collections: <b id="stat-collections">0</b></span>
    <span>Avatars: <b id="stat-avatars">0</b></span>
    <span>OpenSea candidates: <b id="stat-os">0</b></span>
    <span>🟢 <b id="stat-green">0</b></span>
    <span>🟡 <b id="stat-yellow">0</b></span>
    <span>🔴 <b id="stat-red">0</b></span>
    <span>URLs: ✓<b id="stat-alive">0</b> ✗<b id="stat-dead">0</b> 📦<b id="stat-wayback">0</b></span>
    <span>Discord: ✓<b id="stat-dc-alive">0</b> ✗<b id="stat-dc-dead">0</b></span>
    <span>🔒<b id="stat-capped">0</b> 🟢<b id="stat-ongoing">0</b></span>
  </div>
</header>
<div class="controls">
  <input type="text" id="search" placeholder="Search collections, contracts, slugs..." oninput="debounceFilter()">
  <label>Tier:
    <select id="f-tier" onchange="filter()">
      <option value="">All</option>
      <option value="A">A — VRM in metadata</option>
      <option value="B">B — VRM off-chain</option>
      <option value="C">C — WIP</option>
      <option value="arweave">Arweave-native</option>
      <option value="infra">Infrastructure</option>
      <option value="not_vrm">Not VRM</option>
    </select>
  </label>
  <label>Chain:
    <select id="f-chain" onchange="filter()">
      <option value="">All</option>
      <option value="ethereum">Ethereum</option>
      <option value="base">Base</option>
      <option value="optimism">Optimism</option>
      <option value="polygon">Polygon</option>
      <option value="shape">Shape</option>
      <option value="solana">Solana</option>
      <option value="arweave">Arweave</option>
      <option value="multi">Multi-chain</option>
    </select>
  </label>
  <label>License:
    <select id="f-license" onchange="filter()">
      <option value="">All</option>
      <option value="green">🟢 No permission (CC0)</option>
      <option value="yellow">🟡 Holder-based</option>
      <option value="red">🔴 Permission required</option>
      <option value="unknown">Unknown</option>
    </select>
  </label>
  <label>URL:
    <select id="f-url" onchange="filter()">
      <option value="">All</option>
      <option value="alive">✓ Alive</option>
      <option value="dead">✗ Dead</option>
      <option value="error">? Error</option>
      <option value="wayback">📦 Has Wayback</option>
    </select>
  </label>
  <label>Discord:
    <select id="f-discord" onchange="filter()">
      <option value="">All</option>
      <option value="alive">✓ Alive</option>
      <option value="dead">✗ Dead</option>
      <option value="none">— None</option>
    </select>
  </label>
  <label>Supply:
    <select id="f-mint" onchange="filter()">
      <option value="">All</option>
      <option value="capped">🔒 Capped</option>
      <option value="likely_capped">🔒 Likely capped</option>
      <option value="ongoing">🟢 Ongoing</option>
      <option value="no_max_supply">❓ No max</option>
    </select>
  </label>
  <label>Type:
    <select id="f-nfttype" onchange="filter()">
      <option value="">All</option>
      <option value="generative">🎲 Generative</option>
      <option value="1of1_series">🎨 1/1 Series</option>
      <option value="1of1_art">🖼 1/1 Art</option>
      <option value="numbered">🔢 Numbered</option>
      <option value="no_traits">∅ No Traits</option>
    </select>
  </label>
</div>
<div class="tab-bar">
  <div class="tab active" onclick="switchTab('collections')">Collections</div>
  <div class="tab" onclick="switchTab('avatars')">Avatars</div>
  <div class="tab" onclick="switchTab('opensea')">OpenSea Candidates</div>
</div>
<main>
  <div id="collectionsView">
    <table id="collectionsTable">
      <thead>
        <tr>
          <th>Preview</th>
          <th onclick="sort('name')">Collection</th>
          <th onclick="sort('tier')">Tier</th>
          <th onclick="sort('release_date')">Released</th>
          <th onclick="sort('chain')">Chain(s)</th>
          <th onclick="sort('license_category')">License</th>
          <th onclick="sort('vrm_license')">VRM License</th>
          <th>Contract(s)</th>
          <th>OpenSea</th>
          <th onclick="sort('url_status')">URL</th>
          <th onclick="sort('discord_status')">Social</th>
          <th onclick="sort('total_supply')">Total</th>
          <th onclick="sort('num_owners')">Holders</th>
          <th onclick="sort('floor_price')">Floor</th>
          <th onclick="sort('total_volume')">Volume</th>
          <th onclick="sort('category')">Category</th>
          <th onclick="sort('safelist_status')">Verified</th>
          <th onclick="sort('nft_type')">Type</th>
          <th onclick="sort('avatar_count')">Avatars</th>
          <th>VRM</th>
          <th>VRM URL pattern</th>
        </tr>
      </thead>
      <tbody id="collectionsBody"></tbody>
    </table>
  </div>
  <div id="avatarsView">
    <div class="controls" style="border:none;padding:0 0 12px 0">
      <input type="text" id="avatarSearch" placeholder="Search avatars by name or collection..." oninput="filterAvatars()">
      <span class="count" id="avatarCount"></span>
    </div>
    <div class="avatar-grid" id="avatarGrid"></div>
  </div>
  <div id="openseaView">
    <table id="osTable">
      <thead>
        <tr>
          <th>Preview</th>
          <th onclick="sortOS('slug')">Slug</th>
          <th onclick="sortOS('name')">Name</th>
          <th onclick="sortOS('release_date')">Released</th>
          <th onclick="sortOS('chain')">Chain</th>
          <th onclick="sortOS('status')">VRM</th>
          <th onclick="sortOS('url_status')">URL</th>
          <th onclick="sortOS('discord_status')">Social</th>
          <th>VRM param</th>
          <th>VRM</th>
          <th>Contract</th>
          <th>Found via</th>
        </tr>
      </thead>
      <tbody id="osBody"></tbody>
    </table>
  </div>
</main>
<div class="empty" id="emptyState" style="display:none">No results match your filters.</div>

<!-- Image preview modal -->
<div id="imgModal" onclick="closeImgModal()">
  <button id="imgModalClose" onclick="closeImgModal()">&times;</button>
  <div id="imgModalContent">
    <img id="imgModalBanner" src="" style="display:none">
    <img id="imgModalImg" src="">
    <div id="imgModalLabel"></div>
  </div>
</div>

<!-- VRM viewer modal -->
<div id="vrmModal">
  <div id="vrmModalContent">
    <div id="vrmModalHeader">
      <h3 id="vrmModalTitle">VRM Viewer</h3>
      <button id="vrmModalClose" onclick="closeVrmModal()">&times;</button>
    </div>
    <div id="vrmCanvasContainer">
      <canvas id="vrmCanvas"></canvas>
      <div id="vrmLoading">Loading VRM...</div>
      <div id="vrmError"></div>
    </div>
    <div id="vrmModalFooter">
      <span id="vrmFooterInfo"></span>
      <a id="vrmFooterLink" href="#" target="_blank">Open VRM file ↗</a>
    </div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
let sortKey = 'name', sortAsc = true, sortKeyOS = 'slug', sortAscOS = true;
let currentTab = 'collections';

function esc(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : ''; }

function badge(cls, text) { return `<span class="badge badge-${cls}">${esc(text)}</span>`; }

function licenseBadge(cat) {
  const map = { green: '🟢 CC0', yellow: '🟡 Holder', red: '🔴 Restricted', unknown: '?' };
  return badge(cat || 'unknown', map[cat] || '?');
}

function tierBadge(tier) {
  const map = { A: 'A', B: 'B', C: 'C', arweave: 'Arweave', infra: 'Infra', not_vrm: 'Not VRM' };
  return badge(`tier-${tier || 'unknown'}`, map[tier] || tier || '?');
}

let _filterTimer = null;
function debounceFilter() { clearTimeout(_filterTimer); _filterTimer = setTimeout(filter, 150); }

function filter() {
  if (currentTab !== 'collections') return;
  const q = document.getElementById('search').value.toLowerCase();
  const fTier = document.getElementById('f-tier').value;
  const fChain = document.getElementById('f-chain').value;
  const fLicense = document.getElementById('f-license').value;
  const fUrl = document.getElementById('f-url').value;
  const fDiscord = document.getElementById('f-discord').value;
  const fMint = document.getElementById('f-mint').value;
  let rows = DATA.collections.filter(c => {
    if (fTier && c.tier !== fTier) return false;
    if (fChain && c.chain !== fChain) return false;
    if (fLicense && (c.license_category || 'unknown') !== fLicense) return false;
    if (fUrl === 'wayback') { if (!c.wayback_available) return false; }
    else if (fUrl && (c.url_status || '') !== fUrl) return false;
    if (fDiscord === 'none') { if (c.discord_url) return false; }
    else if (fDiscord && (c.discord_status || '') !== fDiscord) return false;
    if (fMint === 'capped') { if (c.mint_status !== 'capped') return false; }
    else if (fMint === 'likely_capped') { if (c.mint_status !== 'likely_capped') return false; }
    else if (fMint === 'ongoing') { if (c.mint_status !== 'ongoing') return false; }
    else if (fMint === 'no_max_supply') { if (c.mint_status !== 'no_max_supply') return false; }
    const fNftType = document.getElementById('f-nfttype').value;
    if (fNftType && (c.nft_type || 'unknown') !== fNftType) return false;
    if (q) {
      const hay = [c.name, c.contract, c.opensea_slug, c.vrm_license, c.creator, c.notes, c.description]
        .join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  rows.sort((a, b) => {
    let va = a[sortKey] || '', vb = b[sortKey] || '';
    if (typeof va === 'number') return sortAsc ? va - vb : vb - va;
    return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
  });
  const tbody = document.getElementById('collectionsBody');
  tbody.innerHTML = rows.map(c => {
    const us = c.url_status;
    const urlIcon = us === 'alive' ? '✓' : us === 'dead' ? '✗' : us === 'error' ? '?' : '—';
    const urlColor = us === 'alive' ? '#56d364' : us === 'dead' ? '#f85149' : '#8b949e';
    const wbLink = c.wayback_available ? ` <a href="https://web.archive.org/web/*/opensea.io/collection/${c.opensea_slug}" target="_blank" title="${c.wayback_snapshots} snapshots">📦</a>` : '';
    const contracts = (c.contracts || []).map(ct => {
      const explorer = ct.chain === 'polygon' ? 'polygonscan' : ct.chain === 'base' ? 'basescan' : ct.chain === 'optimism' ? 'optimistic.etherscan' : 'etherscan';
      return `<a href="https://${explorer}.io/address/${ct.address}" target="_blank" class="mono" title="${ct.chain}">${ct.address.slice(0,6)}..${ct.address.slice(-4)}</a>`;
    }).join(' ');
    const ds = c.discord_status;
    let dIcon = '—', dColor = '#8b949e', dTitle = '';
    if (ds === 'alive') { dIcon = '✓'; dColor = '#56d364'; dTitle = `${c.discord_members||0} members`; }
    else if (ds === 'dead') { dIcon = '✗'; dColor = '#f85149'; dTitle = 'invite expired/revoked'; }
    else if (ds === 'rate_limited') { dIcon = '⏳'; dColor = '#d29922'; dTitle = 'rate limited'; }
    else if (ds === 'error') { dIcon = '?'; dColor = '#8b949e'; }
    const dLink = c.discord_url && ds === 'alive' ? `<a href="${c.discord_url}" target="_blank" style="color:${dColor}" title="${dTitle}">${dIcon}</a>` : `<span style="color:${dColor}" title="${dTitle}">${dIcon}</span>`;
    const tw = c.twitter_username ? ` <a href="https://twitter.com/${c.twitter_username}" target="_blank" title="@${c.twitter_username}">𝕏</a>` : '';
    const img = c.image_url ? `<img class="thumb" loading="lazy" src="${c.image_url}" alt="${esc(c.name)}" onclick="showImg('${c.image_url}','${esc(c.name)}','${c.banner_image_url || ''}')" onerror="this.outerHTML='<span class=\\'thumb-placeholder\\'>🖼</span>'">` : '<span class="thumb-placeholder">🖼</span>';
    const vrmBtn = c.vrm_url_https ? `<button class="vrm-btn" onclick="openVrmViewer('${c.vrm_url_https}','${esc(c.name)}','${esc(c.vrm_url_https)}')" title="View VRM in 3D">▶ VRM</button>` : (c.vrm_url_pattern ? '📋' : '—');
    // Supply/mint status
    const ms = c.mint_status;
    let supplyCell = '—';
    if (c.total_supply) {
      let icon = '❓', color = 'var(--text-muted)', title = '';
      if (ms === 'capped') { icon = '🔒'; color = 'var(--success)'; title = 'Mint complete'; }
      else if (ms === 'likely_capped') { icon = '🔒'; color = 'var(--text-muted)'; title = 'Likely capped (>1yr old)'; }
      else if (ms === 'ongoing') { icon = '🟢'; color = 'var(--warning)'; title = `Ongoing: ${c.mint_progress||0}% minted`; }
      else if (ms === 'no_max_supply') { icon = '❓'; color = 'var(--text-muted)'; title = 'No max supply found'; }
      const maxStr = c.max_supply ? `<span class="mono" style="color:var(--text-muted)">/${c.max_supply}</span>` : '';
      const progStr = ms === 'ongoing' ? ` <span style="color:var(--warning);font-size:11px">(${c.mint_progress||0}%)</span>` : '';
      supplyCell = `<span style="color:${color}" title="${title}">${icon}</span> <b style="color:var(--text-primary)">${c.total_supply.toLocaleString()}</b>${maxStr}${progStr}`;
    }
    // NFT type
    const nftIcons = {generative:'🎲', '1of1_series':'🎨', '1of1_art':'🖼', numbered:'🔢', no_traits:'∅', mixed:'🔀', unknown:'❓'};
    const nftLabels = {generative:'Generative', '1of1_series':'1/1 Series', '1of1_art':'1/1 Art', numbered:'Numbered', no_traits:'No Traits', mixed:'Mixed', unknown:'?'};
    const nt = c.nft_type || 'unknown';
    const nftTitle = nftLabels[nt] + (c.avg_traits ? ` — ${c.avg_traits} avg traits, ${c.trait_types_count||0} types` : '');
    const nftCell = `<span title="${nftTitle}">${nftIcons[nt]||'❓'}</span>`;
    return `<tr>
    <td>${img}</td>
    <td><b>${esc(c.name)}</b>${c.creator ? `<br><span class="mono">${esc(c.creator)}</span>` : ''}</td>
    <td>${tierBadge(c.tier)}</td>
    <td class="mono">${esc(c.release_date || '?')}</td>
    <td>${esc(c.chain || '?')}${(c.contracts||[]).length > 1 ? ` <span class="count">(${(c.contracts||[]).length})</span>` : ''}</td>
    <td>${licenseBadge(c.license_category)}</td>
    <td>${esc(c.vrm_license || '?')}</td>
    <td>${contracts || (c.contract ? `<a href="https://etherscan.io/address/${c.contract}" target="_blank" class="mono">${c.contract.slice(0,6)}..${c.contract.slice(-4)}</a>` : '—')}</td>
    <td>${c.opensea_slug ? `<a href="https://opensea.io/collection/${c.opensea_slug}" target="_blank">${esc(c.opensea_slug)}</a>` : (c.project_url ? `<a href="${c.project_url}" target="_blank">🌐</a>` : '—')}</td>
    <td style="color:${urlColor}">${urlIcon}${wbLink}</td>
    <td>${dLink}${tw}</td>
    <td>${supplyCell}</td>
    <td class="mono">${c.num_owners ? c.num_owners.toLocaleString() : '—'}</td>
    <td class="mono">${c.floor_price ? `${c.floor_price.toFixed(3)} ${esc(c.floor_price_symbol || '')}` : '—'}</td>
    <td class="mono">${c.total_volume ? c.total_volume.toLocaleString(undefined, {maximumFractionDigits:0}) : '—'}</td>
    <td>${esc(c.category || '—')}</td>
    <td>${c.safelist_status === 'verified' ? '<span style="color:var(--success)">✓</span>' : c.safelist_status === 'approved' ? '<span style="color:var(--warning)">~</span>' : '—'}</td>
    <td>${nftCell}</td>
    <td>${c.avatar_count || '—'}</td>
    <td>${vrmBtn}</td>
    <td class="url-cell mono" title="${esc(c.vrm_url_pattern)}">${esc(c.vrm_url_pattern || '—')}</td>
  </tr>
    ${c.description ? `<tr class="desc-row"><td colspan="20" class="desc-cell">${esc(c.description.slice(0,200))}${c.description.length > 200 ? '…' : ''}</td></tr>` : ''}`}).join('');
  document.getElementById('emptyState').style.display = rows.length ? 'none' : 'block';
  document.getElementById('collectionsTable').style.display = rows.length ? '' : 'none';
}

function filterAvatars() {
  const q = (document.getElementById('avatarSearch')?.value || '').toLowerCase();
  let rows = DATA.avatars.filter(a => {
    if (!q) return true;
    const hay = [a.name, a.collection_id, a.description, a.model_file_url].join(' ').toLowerCase();
    return hay.includes(q);
  }).slice(0, 500);
  document.getElementById('avatarCount').textContent = `${rows.length} of ${DATA.avatars.length} shown`;
  document.getElementById('avatarGrid').innerHTML = rows.map(a => `<div class="avatar-card">
    ${a.thumbnail_url ? `<img src="${esc(a.thumbnail_url)}" loading="lazy" alt="${esc(a.name || a.collection_id)}" onerror="this.style.display='none'">` : ''}
    <h4>${esc(a.name)}</h4>
    <div class="mono">${esc(a.collection_id)}</div>
    ${a.model_file_url ? `<a href="${esc(a.model_file_url)}" target="_blank">Download VRM</a>` : ''}
  </div>`).join('');
}

function filterOS() {
  const q = document.getElementById('search').value.toLowerCase();
  let rows = DATA.opensea.filter(c => {
    if (q) {
      const hay = [c.slug, c.name, c.contract, c.vrm_url].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  rows.sort((a, b) => {
    let va = a[sortKeyOS] || '', vb = b[sortKeyOS] || '';
    return sortAscOS ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
  });
  document.getElementById('osBody').innerHTML = rows.map(c => {
    const us = c.url_status;
    const urlIcon = us === 'alive' ? '✓' : us === 'dead' ? '✗' : us === 'error' ? '?' : '—';
    const urlColor = us === 'alive' ? '#56d364' : us === 'dead' ? '#f85149' : '#8b949e';
    const wbLink = c.wayback_available ? ` <a href="https://web.archive.org/web/*/opensea.io/collection/${c.slug}" target="_blank" title="${c.wayback_snapshots} snapshots">📦</a>` : '';
    const ds = c.discord_status;
    let dIcon = '—', dColor = '#8b949e', dTitle = '';
    if (ds === 'alive') { dIcon = '✓'; dColor = '#56d364'; dTitle = `${c.discord_members||0} members`; }
    else if (ds === 'dead') { dIcon = '✗'; dColor = '#f85149'; dTitle = 'expired/revoked'; }
    else if (ds === 'rate_limited') { dIcon = '⏳'; dColor = '#d29922'; }
    const osImg = c.image_url ? `<img class="thumb" src="${c.image_url}" alt="${esc(c.name)}" onclick="showImg('${c.image_url}','${esc(c.name)}','${c.banner_image_url || ''}')" onerror="this.outerHTML='<span class=\\'thumb-placeholder\\'>🖼</span>'">` : '<span class="thumb-placeholder">🖼</span>';
    const osVrmBtn = c.vrm_url_https ? `<button class="vrm-btn" onclick="openVrmViewer('${c.vrm_url_https}','${esc(c.name)}','${esc(c.vrm_url_https)}')">▶ VRM</button>` : '—';
    const osTw = c.twitter_username ? ` <a href="https://twitter.com/${c.twitter_username}" target="_blank" title="@${c.twitter_username}">𝕏</a>` : '';
    return `<tr>
    <td>${osImg}</td>
    <td>${c.slug ? `<a href="https://opensea.io/collection/${c.slug}" target="_blank">${esc(c.slug)}</a>` : '—'}</td>
    <td>${esc(c.name)}</td>
    <td class="mono">${esc(c.release_date || '?')}</td>
    <td>${esc(c.chain || '?')}</td>
    <td>${badge(c.status === 'vrm' ? 'green' : c.status === 'no_vrm' ? 'unknown' : 'yellow', c.status)}</td>
    <td style="color:${urlColor}">${urlIcon}${wbLink}</td>
    <td style="color:${dColor}" title="${dTitle}">${dIcon}${osTw}</td>
    <td class="mono">${esc(c.vrm_param || '—')}</td>
    <td>${osVrmBtn}</td>
    <td class="mono">${c.contract ? `<a href="https://etherscan.io/address/${c.contract}" target="_blank">${c.contract.slice(0,8)}..</a>` : '—'}</td>
    <td class="mono">${esc(c.source_query || '—')}</td>
  </tr>`}).join('');
}

function sort(key) { sortKey = key; sortAsc = !sortAsc; filter(); }
function sortOS(key) { sortKeyOS = key; sortAscOS = !sortAscOS; filterOS(); }

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('collectionsView').style.display = tab === 'collections' ? '' : 'none';
  document.getElementById('avatarsView').style.display = tab === 'avatars' ? '' : 'none';
  document.getElementById('openseaView').style.display = tab === 'opensea' ? '' : 'none';
  if (tab === 'avatars') filterAvatars();
  if (tab === 'opensea') filterOS();
}

// Init stats
document.getElementById('stat-collections').textContent = DATA.collections.length;
document.getElementById('stat-avatars').textContent = DATA.avatars.length;
document.getElementById('stat-os').textContent = DATA.opensea.length;
document.getElementById('stat-green').textContent = DATA.collections.filter(c => c.license_category === 'green').length;
document.getElementById('stat-yellow').textContent = DATA.collections.filter(c => c.license_category === 'yellow').length;
document.getElementById('stat-red').textContent = DATA.collections.filter(c => c.license_category === 'red').length;
document.getElementById('stat-alive').textContent = DATA.opensea.filter(c => c.url_status === 'alive').length;
document.getElementById('stat-dead').textContent = DATA.opensea.filter(c => c.url_status === 'dead').length;
document.getElementById('stat-wayback').textContent = DATA.opensea.filter(c => c.wayback_available).length;
document.getElementById('stat-dc-alive').textContent = DATA.opensea.filter(c => c.discord_status === 'alive').length;
document.getElementById('stat-dc-dead').textContent = DATA.opensea.filter(c => c.discord_status === 'dead').length;
document.getElementById('stat-capped').textContent = DATA.collections.filter(c => c.mint_status === 'capped' || c.mint_status === 'likely_capped').length;
document.getElementById('stat-ongoing').textContent = DATA.collections.filter(c => c.mint_status === 'ongoing').length;
filter();

// ─── Image preview modal ───────────────────────────────────────────────────
function showImg(url, name, bannerUrl) {
  if (!url) return;
  const img = document.getElementById('imgModalImg');
  const banner = document.getElementById('imgModalBanner');
  const label = document.getElementById('imgModalLabel');
  img.src = url;
  img.alt = name || '';
  // Handle video banners (OpenSea allows .mp4 banners)
  const isVideo = bannerUrl && (bannerUrl.includes('.mp4') || bannerUrl.includes('stream.mux.com'));
  if (bannerUrl && !isVideo) {
    banner.src = bannerUrl;
    banner.style.display = '';
  } else {
    banner.style.display = 'none';
    banner.src = '';
  }
  label.textContent = name || '';
  document.getElementById('imgModal').classList.add('active');
}
function closeImgModal() {
  document.getElementById('imgModal').classList.remove('active');
  document.getElementById('imgModalImg').src = '';
  document.getElementById('imgModalBanner').src = '';
}

// ─── VRM viewer modal (Three.js + @pixiv/three-vrm via ES modules) ──────────
// The VRM viewer is loaded as an ES module. Functions are exposed on window.
let vrmAnimId = null;

function showVrmError(msg) {
  document.getElementById('vrmLoading').classList.remove('active');
  const err = document.getElementById('vrmError');
  err.textContent = msg;
  err.classList.add('active');
}

function openVrmViewer(vrmUrl, name, footerInfo) {
  if (!vrmUrl) { alert('No VRM URL available for this collection.'); return; }
  document.getElementById('vrmModalTitle').textContent = 'VRM Viewer — ' + (name || '');
  document.getElementById('vrmModal').classList.add('active');
  document.getElementById('vrmLoading').classList.add('active');
  document.getElementById('vrmError').classList.remove('active');
  document.getElementById('vrmFooterInfo').textContent = footerInfo || '';
  document.getElementById('vrmFooterLink').href = vrmUrl;

  if (window._vrmViewerReady) {
    window._initVrmScene(vrmUrl);
  } else {
    // Load the ES module script
    const s = document.createElement('script');
    s.type = 'module';
    s.textContent = `
      import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
      import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/GLTFLoader.js';
      import { VRM, VRMUtils } from 'https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.3.2/+esm';

      let scene = null, renderer = null, camera = null, model = null;

      window._initVrmScene = function(vrmUrl) {
        const canvas = document.getElementById('vrmCanvas');
        const container = document.getElementById('vrmCanvasContainer');
        const w = container.clientWidth, h = container.clientHeight;

        if (!scene) {
          scene = new THREE.Scene();
          scene.background = new THREE.Color(0x0D0D0F);
          camera = new THREE.PerspectiveCamera(30, w / h, 0.1, 100);
          camera.position.set(0, 1.3, 4);
          camera.lookAt(0, 1.3, 0);
          renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
          renderer.setPixelRatio(window.devicePixelRatio);
          renderer.setSize(w, h);
          const amb = new THREE.AmbientLight(0xffffff, 0.9);
          scene.add(amb);
          const dir = new THREE.DirectionalLight(0xffffff, 0.5);
          dir.position.set(1, 2, 1);
          scene.add(dir);

          // Orbit controls via mouse
          let theta = 0, phi = 0.1, isDragging = false, lastX = 0, lastY = 0;
          canvas.addEventListener('mousedown', e => { isDragging = true; lastX = e.clientX; lastY = e.clientY; });
          window.addEventListener('mouseup', () => { isDragging = false; });
          window.addEventListener('mousemove', e => {
            if (!isDragging) return;
            theta -= (e.clientX - lastX) * 0.01;
            phi = Math.max(-0.5, Math.min(0.8, phi + (e.clientY - lastY) * 0.01));
            lastX = e.clientX; lastY = e.clientY;
            const r = camera.position.length();
            camera.position.set(r * Math.sin(theta) * Math.cos(phi), 1.3 + r * Math.sin(phi), r * Math.cos(theta) * Math.cos(phi));
            camera.lookAt(0, 1.3, 0);
          });
          canvas.addEventListener('wheel', e => {
            e.preventDefault();
            const r = Math.max(1.5, Math.min(10, camera.position.length() + e.deltaY * 0.005));
            camera.position.setLength(r);
          });
        } else if (model) {
          scene.remove(model);
          VRMUtils.deepDispose(model);
          model = null;
        }

        const loader = new GLTFLoader();
        loader.load(vrmUrl, (gltf) => {
          VRM.from(gltf.scene).then((vrm) => {
            model = gltf.scene;
            scene.add(model);
            VRMUtils.removeUnnecessaryVertices(gltf.scene);

            // Reset pose
            vrm.humanoid?.resetNormalizedPose();
            // Face forward
            if (vrm.humanoid) {
              vrm.humanoid.setNormalizedPose();
            }

            const meta = vrm.meta;
            if (meta) {
              const metaName = meta.name || meta.title || 'Unknown';
              document.getElementById('vrmFooterInfo').textContent =
                'VRM: ' + metaName + ' | Author: ' + (meta.authors || meta.author || '?');
            }

            document.getElementById('vrmLoading').classList.remove('active');

            if (vrmAnimId) cancelAnimationFrame(vrmAnimId);
            const clock = new THREE.Clock();
            function animate() {
              vrmAnimId = requestAnimationFrame(animate);
              const delta = clock.getDelta();
              if (model) vrm.update(delta);
              renderer.render(scene, camera);
            }
            animate();
          }).catch(err => {
            showVrmError('Failed to parse VRM: ' + err.message);
          });
        }, undefined, (err) => {
          showVrmError('Failed to load VRM file. The IPFS gateway may be slow or the file may be unavailable. Try the direct link below.');
        });
      };

      window._vrmViewerReady = true;
      // If a URL is already queued, init now
      if (window._pendingVrmUrl) {
        const url = window._pendingVrmUrl;
        window._pendingVrmUrl = null;
        window._initVrmScene(url);
      }
    `;
    document.head.appendChild(s);
    window._pendingVrmUrl = vrmUrl;
  }
}

function closeVrmModal() {
  document.getElementById('vrmModal').classList.remove('active');
  if (vrmAnimId) { cancelAnimationFrame(vrmAnimId); vrmAnimId = null; }
}

// Escape to close modals
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeVrmModal(); closeImgModal(); }
});
</script>
</body>
</html>
"""

def build_html():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    collections = [dict(r) for r in conn.execute("SELECT * FROM collections ORDER BY name")]
    avatars = [dict(r) for r in conn.execute("SELECT id, collection_id, name, description, model_file_url, format, thumbnail_url FROM avatars ORDER BY collection_id, name")]
    opensea = [dict(r) for r in conn.execute("SELECT * FROM opensea_candidates ORDER BY slug")]
    # Load all contracts and group by collection_id
    contracts = {}
    for r in conn.execute("SELECT collection_id, address, chain, is_primary FROM contracts ORDER BY is_primary DESC, chain"):
        cid = r['collection_id']
        if cid not in contracts: contracts[cid] = []
        contracts[cid].append({'address': r['address'], 'chain': r['chain'], 'is_primary': r['is_primary']})
    conn.close()

    # Attach contracts to collections
    for c in collections:
        c['contracts'] = contracts.get(c['id'], [])

    data = {
        'collections': collections,
        'avatars': avatars,
        'opensea': opensea,
    }
    data_json = json.dumps(data)

    html_content = HTML_TEMPLATE.replace("__DATA_JSON__", data_json)
    HTML_PATH.write_text(html_content)
    return len(collections), len(avatars), len(opensea)

# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building SQLite database...")
    stats = build_db()
    print(f"  Collections: {stats['collections']} (Tier A: {stats['tier_a']}, Tier B: {stats['tier_b']})")
    print(f"  Avatars: {stats['avatars']}")
    print(f"  OpenSea candidates: {stats['opensea_candidates']}")
    print(f"  License: 🟢 {stats['green']}, 🟡 {stats['yellow']}, 🔴 {stats['red']}")
    print(f"  URL status: ✓ {stats['urls_alive']} alive, ✗ {stats['urls_dead']} dead, 📦 {stats['wayback_archived']} Wayback archives")
    print(f"  Discord:    ✓ {stats['dc_alive']} alive ({stats['dc_members']:,} members), ✗ {stats['dc_dead']} dead")
    print(f"  Mint:       🔒 {stats['mint_capped']} capped, 🟢 {stats['mint_ongoing']} ongoing")

    print("\nBuilding static HTML catalog...")
    c, a, o = build_html()
    print(f"  index.html: {c} collections, {a} avatars, {o} OpenSea candidates")
    print(f"  Size: {HTML_PATH.stat().st_size // 1024}KB")

    # Backfill missing project_urls from A3AC/ToxSam/known sources
    import subprocess
    subprocess.run([sys.executable, str(BASE / "backfill_urls.py")],
                   capture_output=True, text=True)

    # Fetch images for open-source avatar collections from ToxSam GitHub
    subprocess.run([sys.executable, str(BASE / "fetch_osavatar_images.py")],
                   capture_output=True, text=True)

    # Fetch collection meta (descriptions, num_owners, floor_price, etc.) from OpenSea API
    subprocess.run([sys.executable, str(BASE / "fetch_collection_meta.py")],
                   capture_output=True, text=True)

    print(f"\nDone. Open index.html in a browser, or use search.py for CLI queries.")
