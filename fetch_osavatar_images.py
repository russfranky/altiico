#!/usr/bin/env python3
"""
Fetch collection images for open-source avatar collections from the
ToxSam/open-source-avatars GitHub repository.
"""
import json, sqlite3, urllib.request, time
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"

def github_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "superyeti/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def normalize(n):
    return n.lower().strip().replace("-", " ").replace("_", " ")

def main():
    url = "https://raw.githubusercontent.com/ToxSam/open-source-avatars/main/data/projects.json"
    projects = github_fetch(url)

    images = {}
    for p in projects:
        name = p.get("name", "")
        data_file = p.get("avatar_data_file", "")
        if not data_file:
            continue
        try:
            avurl = f"https://raw.githubusercontent.com/ToxSam/open-source-avatars/main/data/{data_file}"
            avdata = github_fetch(avurl)
            img = ""
            if isinstance(avdata, list) and avdata:
                img = avdata[0].get("thumbnail_url", "") or avdata[0].get("image_url", "") or avdata[0].get("preview_image", "")
            elif isinstance(avdata, dict):
                img = avdata.get("thumbnail_url", "") or avdata.get("image_url", "") or avdata.get("preview_image", "")
            if img:
                images[name] = img
                print(f"  {name}: {img[:70]}")
            time.sleep(0.3)
        except Exception as e:
            print(f"  {name}: ERROR {str(e)[:40]}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name FROM collections WHERE image_url IS NULL OR image_url = ''").fetchall()

    img_by_norm = {normalize(k): v for k, v in images.items()}

    updated = 0
    for row in rows:
        name_norm = normalize(row["name"])
        img = img_by_norm.get(name_norm)
        if not img:
            for key, val in img_by_norm.items():
                if key in name_norm or name_norm in key:
                    img = val
                    break
        if img:
            conn.execute("UPDATE collections SET image_url=? WHERE id=?", (img, row["id"]))
            print(f"  IMG {row['name']}: {img[:60]}")
            updated += 1

    conn.commit()
    conn.close()
    print(f"\nUpdated {updated} collection images from ToxSam GitHub")

if __name__ == "__main__":
    main()
