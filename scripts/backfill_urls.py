#!/usr/bin/env python3
"""
Backfill missing project_url, description, and license from source data:
1. A3AC parsed data (os_scrape/a3ac_parsed.json)
2. ToxSam open-source-avatars (fetched from GitHub)
3. scraper-toolkit vipe-archive (for VIPE/CryptoAvatars collections)
"""
import json, sqlite3, urllib.request
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"

def normalize_name(n):
    return n.lower().strip().replace('-', ' ').replace('_', ' ')

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Get all collections missing project_url or description
    rows = conn.execute("""
        SELECT id, name, project_url, description, license_category, source
        FROM collections
        WHERE project_url IS NULL OR project_url = ''
           OR description IS NULL OR description = ''
        ORDER BY name
    """).fetchall()

    # Build lookup by normalized name
    by_name = {normalize_name(r['name']): r for r in rows}

    # Sub-entry URL inheritance (side-chain variants, VRM file variants)
    sub_fixes = [
        ('https://opensourceavatars.com/', ['NeonGlitch86 Collection', 'NeonGlitch86 Collection (Polygon side)', 'NeonGlitch86 Collection (Shape side)', 'Xmas Chibis (VRM file)', 'Halloween Rising (VRM file)', 'ToxSam (Base side)']),
        ('https://retrodoges.com/mint', ['Retro Doges']),
    ]
    for url, names in sub_fixes:
        for name in names:
            row = by_name.get(normalize_name(name))
            if row and not row['project_url']:
                conn.execute("UPDATE collections SET project_url=? WHERE id=?", (url, row['id']))
                by_name.pop(normalize_name(name), None)

    if not rows:
        return

    # ─── Source 1: A3AC parsed data ──────────────────────────────────────
    a3ac_path = BASE / "os_scrape" / "a3ac_parsed.json"
    if a3ac_path.exists():
        a3ac = json.load(open(a3ac_path))
        for entry in a3ac:
            ename = normalize_name(entry.get('name', ''))
            url = entry.get('project_url', '') or entry.get('website', '') or entry.get('url', '')
            desc = entry.get('description', '') or entry.get('notes', '')
            license_cat = entry.get('license_category', '')
            # Try exact match
            row = by_name.get(ename)
            # Also try partial matches
            if not row:
                for key, r in by_name.items():
                    if ename in key or key in ename:
                        row = r
                        break
            if row:
                updated = False
                if url and (not row['project_url']):
                    conn.execute("UPDATE collections SET project_url=? WHERE id=?", (url, row['id']))
                    print(f"  🔗 {row['name']}: {url}")
                    updated = True
                if desc and (not row['description']) and len(desc) > 20:
                    conn.execute("UPDATE collections SET description=? WHERE id=?", (desc[:500], row['id']))
                    updated = True
                if license_cat and row['license_category'] in (None, '', 'unknown'):
                    conn.execute("UPDATE collections SET license_category=? WHERE id=?", (license_cat, row['id']))
                    updated = True
                if updated:
                    by_name.pop(normalize_name(row['name']), None)

    # ─── Source 2: ToxSam open-source-avatars ────────────────────────────
    try:
        url = 'https://raw.githubusercontent.com/ToxSam/open-source-avatars/main/data/projects.json'
        data = json.loads(urllib.request.urlopen(url, timeout=15).read())
        # Also fetch individual avatar JSONs for more detail
        for p in data:
            pname = normalize_name(p.get('name', ''))
            purl = p.get('website', '') or p.get('url', '') or p.get('projectUrl', '')
            plicense = p.get('license', '')
            pdesc = p.get('description', '') or p.get('about', '')
            row = by_name.get(pname)
            if not row:
                for key, r in by_name.items():
                    if pname in key or key in pname:
                        row = r
                        break
            if row:
                updated = False
                if purl and not row['project_url']:
                    conn.execute("UPDATE collections SET project_url=? WHERE id=?", (purl, row['id']))
                    print(f"  🔗 {row['name']}: {purl}")
                    updated = True
                if pdesc and not row['description'] and len(pdesc) > 20:
                    conn.execute("UPDATE collections SET description=? WHERE id=?", (pdesc[:500], row['id']))
                    updated = True
                if plicense and row['license_category'] in (None, '', 'unknown'):
                    conn.execute("UPDATE collections SET license_category=? WHERE id=?", (plicense, row['id']))
                    updated = True
                if updated:
                    by_name.pop(normalize_name(row['name']), None)
    except Exception as e:
        print(f"ToxSam fetch failed: {e}")

    # ─── Source 3: Known URLs from research ──────────────────────────────
    known_urls = {
        '100avatars r1': 'https://github.com/PolygonalMind/100Avatars',
        '100avatars r2': 'https://github.com/PolygonalMind/100Avatars',
        '100avatars r3': 'https://github.com/PolygonalMind/100Avatars',
        'vipe heroes genesis': 'https://vipe.io/',
        'grifters squaddies': 'https://vipe.io/',
        'toxsam': 'https://opensourceavatars.com/',
        'halloween rising': 'https://opensourceavatars.com/',
        'xmas chibis': 'https://opensourceavatars.com/',
        'neonglitch86 collection': 'https://opensourceavatars.com/',
        'metatravelers': 'https://metatravelers.xyz/',
        'metaani (metaanigen)': 'https://conata.world/metaani/gen',
        'pixelbeasts (beastopia)': 'https://www.pixelbeasts.co/',
        'polygonlow': 'https://polygonlow.xyz/',
        'retrodoges': 'https://retrodoges.com/mint',
    }
    for name_key, url in known_urls.items():
        row = by_name.get(name_key)
        if not row:
            for key, r in by_name.items():
                if name_key in key or key in name_key:
                    row = r
                    break
        if row and not row['project_url']:
            conn.execute("UPDATE collections SET project_url=? WHERE id=?", (url, row['id']))
            print(f"  🔗 {row['name']}: {url}")
            by_name.pop(normalize_name(row['name']), None)

    # ─── Source 4: Manual image fixes for collections without OpenSea images ──
    manual_images = {
        'MetaTravelers': ('metatravelers', 'https://i2c.seadn.io/ethereum/8d2c0cf48a834b7d9c4bc33e66e05f8c/4021aa6a4c6acc98964602a4b037ee/bb4021aa6a4c6acc98964602a4b037ee.gif'),
        'PixelBeasts (Beastopia)': ('pixelbeasts', 'https://i2c.seadn.io/collection/pixelbeasts/image/c0c371523b31aec1a3cabd6db62ef1'),
        'RetroDoge': ('retrodoges', 'https://i2c.seadn.io/collection/retrodoges/image/f32f05bf9f60f80712d3c338870af1/'),
        'Metaani (MetaaniGEN)': ('metaanigen', 'https://i2c.seadn.io/ethereum/299a4d5b8f3547559afa14673e46cd2c/9eef987ccc5b177b3'),
        'MetaaniGEN': ('metaanigen', 'https://i2c.seadn.io/ethereum/299a4d5b8f3547559afa14673e46cd2c/9eef987ccc5b177b3'),
        'mferverse: OG mfers': ('mferverse-og-mfers', 'https://i2c.seadn.io/ethereum/413ab93b3ef84e05b4011ba6c30d73f3/a9f34cfe44eaae3c3d49ddcfb57295/3ca9f34cfe44eaae3c3d49ddcfb57295.png'),
    }
    for name, (slug, img) in manual_images.items():
        row = conn.execute("SELECT id FROM collections WHERE name=? AND (image_url IS NULL OR image_url='')", (name,)).fetchone()
        if row:
            conn.execute("UPDATE collections SET image_url=?, opensea_slug=? WHERE id=?", (img, slug, row['id']))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
