#!/usr/bin/env python3
"""Parse the awesome-3D-avatar-collections README and enrich our database.

Extracts from the A3AC table:
  - Creator name + project URL
  - Contract address (from etherscan link)
  - Metadata URL (sample token metadata)
  - Metadata param (vrm_url, avatar_url, files, etc.)
  - Preview image URL
  - VRM support (✔️ or ❌)

Cross-references with existing collections by contract address.
Fills in missing: project_url, metadata_url, vrm_param, preview images.
Also adds any collections we don't have yet.
"""
import sqlite3, json, re, sys
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "vrm_index.db"
README = BASE / "os_scrape" / "a3ac_readme.md"

def parse_table(md_text):
    """Parse markdown table rows into dicts."""
    rows = []
    for line in md_text.split('\n'):
        line = line.strip()
        if not line.startswith('|') or '---' in line:
            continue
        # Skip header
        if 'Creator' in line and 'Contract' in line:
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) < 6:
            continue
        rows.append({
            'creator_cell': cells[0],
            'contract_cell': cells[1],
            'metadata_cell': cells[2],
            'param_cell': cells[3],
            'preview_cell': cells[4],
            'vrm_cell': cells[5],
        })
    return rows

def extract_link(cell):
    """Extract first markdown link URL from a cell."""
    m = re.search(r'\[([^\]]*)\]\(([^)]+)\)', cell)
    if m:
        return {'text': m.group(1), 'url': m.group(2)}
    return None

def extract_image(cell):
    """Extract image URL from a markdown image cell."""
    m = re.search(r'!\[[^\]]*\]\(([^)]+)\)', cell)
    if m:
        return m.group(1)
    return None

def extract_contract(cell):
    """Extract contract address from etherscan link."""
    m = re.search(r'0x[0-9a-fA-F]{40}', cell)
    return m.group(0) if m else None

def extract_vrm_param(cell):
    """Extract VRM metadata param name."""
    if 'No metadata' in cell or 'N/A' in cell or 'No Token' in cell:
        return None
    # Extract param names like vrm_url, avatar_url, files, model/vrm, asset, vrm
    params = []
    for m in re.finditer(r'`([^`]+)`', cell):
        params.append(m.group(1))
    if not params:
        # Try to find VRM: or GLB: prefixes
        for m in re.finditer(r'(?:VRM|GLB):\s*(\S+)', cell):
            params.append(m.group(1))
    return params[0] if params else None

def main():
    if not README.exists():
        print("README not found. Run: curl -sS https://raw.githubusercontent.com/itsmetamike/awesome-3D-avatar-collections/main/README.md -o os_scrape/a3ac_readme.md", file=sys.stderr)
        return

    md = README.read_text()
    rows = parse_table(md)
    print(f"Parsed {len(rows)} collections from A3AC README", file=sys.stderr)

    # Parse each row
    entries = []
    for row in rows:
        creator = extract_link(row['creator_cell'])
        contract = extract_contract(row['contract_cell'])
        metadata = extract_link(row['metadata_cell'])
        preview = extract_image(row['preview_cell'])
        vrm_param = extract_vrm_param(row['param_cell'])
        has_vrm = '✔' in row['vrm_cell']
        # Check for † (partial/limited VRM)
        partial_vrm = '†' in row['vrm_cell']

        entries.append({
            'name': creator['text'] if creator else '',
            'project_url': creator['url'] if creator else '',
            'contract': contract,
            'metadata_url': metadata['url'] if metadata else '',
            'vrm_param': vrm_param,
            'preview_image': preview,
            'has_vrm': has_vrm,
            'partial_vrm': partial_vrm,
            'param_raw': row['param_cell'],
        })

    # Save parsed data
    json.dump(entries, open(BASE / "os_scrape" / "a3ac_parsed.json", "w"), indent=2)

    # Cross-reference with DB
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # Build contract -> collection_id map
    contract_map = {}
    for r in conn.execute("SELECT id, name, contract, opensea_slug FROM collections"):
        if r['contract'] and len(r['contract']) >= 20:
            contract_map[r['contract'].lower()] = dict(r)

    matched = 0
    new_entries = 0
    updated = 0

    for e in entries:
        if not e['contract']:
            continue

        contract_lower = e['contract'].lower()
        if contract_lower in contract_map:
            matched += 1
            c = contract_map[contract_lower]

            # Fill in missing fields
            updates = {}
            if not c.get('opensea_slug') and e['project_url']:
                # We can't get the slug from here, but we can store project_url
                pass

            # Check if we need to add project_url column
            try:
                conn.execute("ALTER TABLE collections ADD COLUMN project_url TEXT")
            except sqlite3.OperationalError:
                pass

            # Update project_url if missing
            if e['project_url']:
                r = conn.execute("SELECT project_url FROM collections WHERE id=?", (c['id'],)).fetchone()
                if not r or not r['project_url']:
                    conn.execute("UPDATE collections SET project_url=? WHERE id=?", (e['project_url'], c['id']))
                    updated += 1

            # Update preview image if missing
            if e['preview_image']:
                r = conn.execute("SELECT image_url FROM collections WHERE id=?", (c['id'],)).fetchone()
                if not r or not r['image_url']:
                    conn.execute("UPDATE collections SET image_url=? WHERE id=?", (e['preview_image'], c['id']))
                    updated += 1

            # Update vrm_param if missing
            if e['vrm_param']:
                r = conn.execute("SELECT vrm_param FROM collections WHERE id=?", (c['id'],)).fetchone()
                if not r or not r['vrm_param']:
                    conn.execute("UPDATE collections SET vrm_param=? WHERE id=?", (e['vrm_param'], c['id']))
                    updated += 1

            # Update metadata_url if we add that column
            if e['metadata_url']:
                try:
                    conn.execute("ALTER TABLE collections ADD COLUMN sample_metadata_url TEXT")
                except sqlite3.OperationalError:
                    pass
                r = conn.execute("SELECT sample_metadata_url FROM collections WHERE id=?", (c['id'],)).fetchone()
                if not r or not r['sample_metadata_url']:
                    conn.execute("UPDATE collections SET sample_metadata_url=? WHERE id=?", (e['metadata_url'], c['id']))
                    updated += 1
        else:
            # New collection not in our DB
            new_entries += 1
            print(f"  NEW: {e['name']:40s} contract={e['contract'][:12]}.. vrm={'✔' if e['has_vrm'] else '✗'}", file=sys.stderr)

    conn.commit()

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  Parsed from A3AC:  {len(entries)}", file=sys.stderr)
    print(f"  Matched to DB:     {matched}", file=sys.stderr)
    print(f"  Updated:           {updated}", file=sys.stderr)
    print(f"  New (not in DB):   {new_entries}", file=sys.stderr)
    print(f"  VRM collections:   {sum(1 for e in entries if e['has_vrm'])}", file=sys.stderr)
    print(f"  Non-VRM (GLB only):{sum(1 for e in entries if not e['has_vrm'])}", file=sys.stderr)

    # Show new entries that have VRM
    vrm_new = [e for e in entries if e['has_vrm'] and e['contract'] and e['contract'].lower() not in contract_map]
    if vrm_new:
        print(f"\n  New VRM collections not in our DB:", file=sys.stderr)
        for e in vrm_new:
            print(f"    {e['name']:40s} {e['contract'][:12]}.. param={e['vrm_param']}", file=sys.stderr)

    # Show non-VRM collections (might still be useful)
    non_vrm = [e for e in entries if not e['has_vrm']]
    if non_vrm:
        print(f"\n  Non-VRM 3D avatar collections (GLB only):", file=sys.stderr)
        for e in non_vrm:
            print(f"    {e['name']:40s} {e['contract'][:12]}.. param={e['param_raw'][:40]}", file=sys.stderr)

    conn.close()

if __name__ == "__main__":
    main()
