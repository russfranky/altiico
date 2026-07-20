#!/usr/bin/env python3
"""
Recover metadata (og:image, description, og:title) for collections with dead
project URLs by fetching archived snapshots from the Wayback Machine.

Uses the Wayback availability API to find the closest snapshot, then extracts
Open Graph meta tags from the archived HTML.

For full site recovery (images, CSS, JS), use the scraper-toolkit:
  https://github.com/russfranky/scraper-toolkit
  node scripts/recover-site.js <domain>
"""
import json, sqlite3, urllib.request, urllib.error, re, time, html
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"
CACHE = BASE / "os_scrape" / "wayback_metadata.json"

def wayback_availability(url):
    """Check if Wayback has a snapshot of this URL."""
    api = f"https://archive.org/wayback/available?url={url}"
    try:
        with urllib.request.urlopen(api, timeout=15) as r:
            data = json.loads(r.read())
        snap = data.get('archived_snapshots', {}).get('closest', {})
        if snap.get('available') and snap.get('url'):
            return snap['url']
    except Exception:
        pass
    return None

def fetch_archived_html(wayback_url):
    """Fetch HTML from a Wayback snapshot."""
    try:
        req = urllib.request.Request(wayback_url, headers={'User-Agent': 'Mozilla/5.0 (superyeti-recovery/1.0)'})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None

def extract_meta(html_text):
    """Extract og:image, og:description, description, og:title from HTML."""
    meta = {}
    # og:image
    m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
    if not m:
        m = re.search(r'<meta\s+name=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
    if m:
        meta['og_image'] = html.unescape(m.group(1))
    # og:description
    m = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
    if m:
        meta['og_description'] = html.unescape(m.group(1))
    # meta description
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
    if m:
        meta['description'] = html.unescape(m.group(1))
    # og:title
    m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
    if m:
        meta['og_title'] = html.unescape(m.group(1))
    # twitter:image
    m = re.search(r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
    if m:
        meta['twitter_image'] = html.unescape(m.group(1))
    # title
    m = re.search(r'<title>([^<]+)</title>', html_text, re.I)
    if m:
        meta['title'] = html.unescape(m.group(1)).strip()
    return meta

def clean_wayback_url(url, wayback_url):
    """Convert a Wayback image URL back to the original URL if possible."""
    # Wayback wraps URLs like: https://web.archive.org/web/20240101/https://example.com/img.png
    # For og:image, we want the original URL (it may still work if archived)
    if '/web/' in url and 'archive.org' in url:
        parts = url.split('/', 4)
        if len(parts) >= 5:
            return parts[4]  # The original URL after the timestamp
    return url

def main():
    cache = json.load(open(CACHE)) if CACHE.exists() else {}

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Find collections with dead project URLs
    rows = conn.execute("""
        SELECT id, name, project_url, image_url, description
        FROM collections
        WHERE project_url LIKE 'http%'
        ORDER BY name
    """).fetchall()

    # Known dead domains (from URL check)
    dead_domains = {
        'adworld.game', 'akutars.com', 'cryptoavatars.io', 'flooz.trade',
        'metatravelers.xyz', 'conata.world', 'lucii.io', 'pape.xyz',
        'rstlss.xyz', 'arbidudes.com', 'arbibots.xyz', 'fluf.world',
        'woodiesofficial.com', 'scatter.art', 'jadu.ar',
    }

    # URL variants to try (www. prefix often has snapshots when bare domain doesn't)
    def url_variants(url):
        variants = [url]
        parsed = urlparse(url)
        if not parsed.netloc.startswith('www.'):
            variants.append(url.replace(f'://{parsed.netloc}', f'://www.{parsed.netloc}'))
        return variants

    recovered = 0
    for row in rows:
        url = row['project_url']
        domain = urlparse(url).netloc.lower().lstrip('www.')
        if domain not in dead_domains:
            continue
        # Skip if we already have image and description
        if row['image_url'] and row['description']:
            continue

        name = row['name']
        # Check cache
        cache_key = url
        if cache_key in cache:
            meta = cache[cache_key]
        else:
            # Find Wayback snapshot — try URL variants
            wayback = None
            for variant in url_variants(url):
                wayback = wayback_availability(variant)
                if wayback:
                    break
            if not wayback:
                print(f"  ✗ {name}: no Wayback snapshot for {url}")
                cache[cache_key] = {}
                continue

            # Fetch archived HTML
            html_text = fetch_archived_html(wayback)
            if not html_text:
                print(f"  ✗ {name}: failed to fetch {wayback}")
                cache[cache_key] = {}
                continue

            # Extract metadata
            meta = extract_meta(html_text)
            meta['wayback_url'] = wayback
            cache[cache_key] = meta
            time.sleep(1)  # Be polite

        # Apply recovered data
        updates = []
        params = []
        if not row['image_url']:
            img = meta.get('og_image') or meta.get('twitter_image')
            if img:
                # Use Wayback URL for the image (original may be dead)
                if 'archive.org' not in img:
                    ts = meta.get('wayback_url', '').split('/web/')[1].split('/')[0] if '/web/' in meta.get('wayback_url', '') else ''
                    if ts and img.startswith('http'):
                        img = f"https://web.archive.org/web/{ts}/{img}"
                updates.append("image_url=?")
                params.append(img)
                print(f"  🖼️  {name}: {img[:80]}")
        if not row['description']:
            desc = meta.get('og_description') or meta.get('description')
            if desc and len(desc) > 20:
                # Filter out spam/hijacked content
                spam_markers = ['situs judi', 'slot gacor', 'sbobet', 'casino', 'poker online', 'judi online']
                if any(s in desc.lower() for s in spam_markers):
                    print(f"  ⚠️  {name}: skipped spam description")
                else:
                    updates.append("description=?")
                    params.append(desc[:500])
                    print(f"  📝 {name}: {desc[:60]}...")

        if updates:
            params.append(row['id'])
            conn.execute(f"UPDATE collections SET {', '.join(updates)} WHERE id=?", params)
            recovered += 1

    # Save cache
    json.dump(cache, open(CACHE, 'w'), indent=2)
    conn.commit()
    conn.close()
    print(f"\nRecovered metadata for {recovered} collections")

if __name__ == "__main__":
    main()
