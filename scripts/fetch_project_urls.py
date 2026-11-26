#!/usr/bin/env python3
"""
Fetch external_url (project website) from OpenSea API for all collections
that have a slug but no project_url. Also fills in missing descriptions.
"""
import json, os, sqlite3, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT
DB = ROOT / "data" / "vrm_index.db"
DETAILS = BASE / "data" / "os_scrape" / "collection_details.json"
API_KEY_PATH = Path.home() / ".opensea" / "api_key"
OSK = ""


def load_opensea_key() -> str:
    env_key = os.environ.get("OPENSEA_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        key = API_KEY_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise SystemExit(f"No OpenSea API key at {API_KEY_PATH}") from exc
    if not key:
        raise SystemExit(f"Empty OpenSea API key at {API_KEY_PATH}")
    return key


def get_opensea_key() -> str:
    global OSK
    if not OSK:
        OSK = load_opensea_key()
    return OSK


def os_fetch(url):
    req = urllib.request.Request(url, headers={"X-API-KEY": get_opensea_key(), "User-Agent": "superyeti/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def main():
    get_opensea_key()
    # Load existing details
    if DETAILS.exists():
        with open(DETAILS, encoding="utf-8") as df:
            details = json.load(df)
    else:
        details = {}

    # Find collections with slug but no project_url
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, name, opensea_slug, project_url, description, chain, contract
        FROM collections
        WHERE opensea_slug IS NOT NULL AND opensea_slug != ''
        ORDER BY name
    """).fetchall()

    updated = 0
    for row in rows:
        slug = row['opensea_slug']
        needs_url = not row['project_url']
        needs_desc = not row['description']
        if not needs_url and not needs_desc:
            continue

        # Check if we already have external_url in details
        d = details.get(slug, {})
        ext_url = d.get('external_url', '')

        if not ext_url:
            # Fetch from OpenSea API
            try:
                url = f"https://api.opensea.io/api/v2/collections/{slug}"
                data = os_fetch(url)
                ext_url = data.get('external_url', '') or ''
                # Update details cache
                d['external_url'] = ext_url
                if data.get('description') and not d.get('description'):
                    d['description'] = data['description']
                details[slug] = d
                time.sleep(0.3)
            except urllib.error.HTTPError as e:
                if e.code in (401, 404):
                    # Slug doesn't exist on OpenSea — skip silently
                    pass
                else:
                    print(f"  ✗ {row['name']}: HTTP {e.code}")
                continue
            except Exception as e:
                print(f"  ✗ {row['name']}: {e}")
                continue

        if ext_url and needs_url:
            conn.execute("UPDATE collections SET project_url=? WHERE id=?", (ext_url, row['id']))
            print(f"  🔗 {row['name']}: {ext_url}")
            updated += 1

    # Save updated details
    DETAILS.parent.mkdir(parents=True, exist_ok=True)
    with open(DETAILS, "w", encoding="utf-8") as df:
        json.dump(details, df, indent=2)
    conn.commit()
    conn.close()
    print(f"\nUpdated {updated} project URLs")

if __name__ == "__main__":
    main()
