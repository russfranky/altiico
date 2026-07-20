#!/usr/bin/env python3
"""Check if OpenSea collection URLs are alive or dead (for Wayback Machine prioritization).

Checks https://opensea.io/collection/{slug} for each slug in the database.
OpenSea returns 200 for valid collections, 404 for dead/delisted ones, and
sometimes 999 (rate limit) or redirects.

Outputs:
  - opensea_url_status.json (per-slug status, HTTP code, final URL, wayback URL)
  - Updates vrm_index.db with url_status column on opensea_candidates
"""
import sqlite3, json, urllib.request, urllib.error, concurrent.futures, time, sys
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"
OUT = BASE / "opensea_url_status.json"

def check_url(slug, timeout=15):
    url = f"https://opensea.io/collection/{slug}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = r.getcode()
            final_url = r.url
            # Read a small chunk to check it's not a soft 404
            body = r.read(5000).decode('utf-8', errors='replace')
            # OpenSea 404 pages sometimes return 200 with error content
            if 'Page not found' in body or 'could not be found' in body.lower():
                return {'slug': slug, 'url': url, 'status': 'dead', 'http_code': code, 'final_url': final_url}
            return {'slug': slug, 'url': url, 'status': 'alive', 'http_code': code, 'final_url': final_url}
    except urllib.error.HTTPError as e:
        return {'slug': slug, 'url': url, 'status': 'dead' if e.code in (404, 410) else 'error', 'http_code': e.code, 'final_url': url}
    except urllib.error.URLError as e:
        return {'slug': slug, 'url': url, 'status': 'error', 'http_code': 0, 'final_url': url, 'error': str(e)}
    except Exception as e:
        return {'slug': slug, 'url': url, 'status': 'error', 'http_code': 0, 'final_url': url, 'error': str(e)}

def check_wayback(slug):
    """Check if Wayback Machine has an archived snapshot."""
    url = f"https://opensea.io/collection/{slug}"
    api = f"https://archive.org/wayback/available?url={urllib.request.quote(url, safe='')}"
    try:
        req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
            snap = d.get('archived_snapshots', {}).get('closest', {})
            if snap and snap.get('available'):
                return snap.get('url', '')
    except:
        pass
    return None

def main():
    conn = sqlite3.connect(str(DB))
    slugs = [r[0] for r in conn.execute(
        "SELECT DISTINCT slug FROM opensea_candidates WHERE slug IS NOT NULL AND slug != '' "
        "UNION SELECT DISTINCT opensea_slug FROM collections WHERE opensea_slug IS NOT NULL AND opensea_slug != ''"
    )]
    conn.close()
    slugs = sorted(set(slugs))
    print(f"Checking {len(slugs)} OpenSea collection URLs...", file=sys.stderr)

    results = []
    # Check in parallel with limited concurrency (OpenSea rate-limits)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(check_url, s): s for s in slugs}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            results.append(r)
            done += 1
            status_icon = {'alive': '✓', 'dead': '✗', 'error': '?'}.get(r['status'], '?')
            if done % 20 == 0 or r['status'] != 'alive':
                print(f"  [{done}/{len(slugs)}] {status_icon} {r['slug']} → {r['http_code']} ({r['status']})", file=sys.stderr)
            # Small delay to avoid rate limiting
            time.sleep(0.1)

    results.sort(key=lambda r: r['slug'])

    # Check Wayback for dead/error URLs
    dead = [r for r in results if r['status'] in ('dead', 'error')]
    print(f"\nChecking Wayback Machine for {len(dead)} dead/error URLs...", file=sys.stderr)
    for r in dead:
        wb = check_wayback(r['slug'])
        r['wayback_url'] = wb
        if wb:
            print(f"  📦 {r['slug']} → archived: {wb[:80]}", file=sys.stderr)
        else:
            print(f"  📦 {r['slug']} → no archive found", file=sys.stderr)
        time.sleep(0.3)

    # Save results
    json.dump(results, open(OUT, 'w'), indent=2)

    # Update database
    conn = sqlite3.connect(str(DB))
    try:
        conn.execute("ALTER TABLE opensea_candidates ADD COLUMN url_status TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE opensea_candidates ADD COLUMN wayback_url TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE collections ADD COLUMN url_status TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE collections ADD COLUMN wayback_url TEXT")
    except sqlite3.OperationalError:
        pass

    for r in results:
        conn.execute("UPDATE opensea_candidates SET url_status=?, wayback_url=? WHERE slug=?",
                      (r['status'], r.get('wayback_url'), r['slug']))
        conn.execute("UPDATE collections SET url_status=?, wayback_url=? WHERE opensea_slug=?",
                      (r['status'], r.get('wayback_url'), r['slug']))
    conn.commit()
    conn.close()

    # Summary
    alive = sum(1 for r in results if r['status'] == 'alive')
    dead_count = sum(1 for r in results if r['status'] == 'dead')
    error_count = sum(1 for r in results if r['status'] == 'error')
    wayback_count = sum(1 for r in results if r.get('wayback_url'))

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Results saved to {OUT}", file=sys.stderr)
    print(f"  ✓ Alive:   {alive}", file=sys.stderr)
    print(f"  ✗ Dead:    {dead_count}", file=sys.stderr)
    print(f"  ? Error:   {error_count}", file=sys.stderr)
    print(f"  📦 Wayback: {wayback_count} archives found for dead/error URLs", file=sys.stderr)
    print(f"  Database updated with url_status + wayback_url columns", file=sys.stderr)

if __name__ == "__main__":
    main()
