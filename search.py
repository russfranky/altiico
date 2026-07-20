#!/usr/bin/env python3
"""Search the VRM collection index from the command line.

Usage:
  python3 search.py [query] [filters]

Examples:
  python3 search.py                          # list all collections
  python3 search.py boombox                  # search by name
  python3 search.py --license green          # CC0 only
  python3 search.py --chain ethereum         # Ethereum only
  python3 search.py --tier A                 # Tier A only
  python3 search.py --license green --chain base
  python3 search.py --contract 0xb67ff       # search by contract prefix
  python3 search.py --opensea                # show OpenSea candidates
  python3 search.py --opensea --status vrm   # OpenSea candidates with VRM
  python3 search.py --avatars grifters       # search avatars
  python3 search.py --stats                  # show index statistics
  python3 search.py --json                   # output as JSON
"""
import sqlite3, argparse, json, sys, os
from pathlib import Path

DB = Path(__file__).parent / "vrm_index.db"

def query_collections(args):
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM collections WHERE 1=1"
    params = []
    if args.query:
        sql += " AND (name LIKE ? OR contract LIKE ? OR opensea_slug LIKE ? OR vrm_license LIKE ? OR creator LIKE ? OR notes LIKE ?)"
        p = f"%{args.query}%"
        params.extend([p, p, p, p, p, p])
    if args.license:
        sql += " AND license_category = ?"
        params.append(args.license)
    if args.chain:
        sql += " AND chain = ?"
        params.append(args.chain)
    if args.tier:
        sql += " AND tier = ?"
        params.append(args.tier)
    if args.contract:
        sql += " AND contract LIKE ?"
        params.append(f"%{args.contract}%")
    if args.url_status:
        sql += " AND url_status = ?"
        params.append(args.url_status)
    if args.discord == "none":
        sql += " AND (discord_url IS NULL OR discord_url = '')"
    elif args.discord:
        sql += " AND discord_status = ?"
        params.append(args.discord)
    if args.mint:
        sql += " AND mint_status = ?"
        params.append(args.mint)
    if args.nft_type:
        sql += " AND nft_type = ?"
        params.append(args.nft_type)
    if args.wayback:
        sql += " AND wayback_available = 1"
    if args.since:
        sql += " AND release_date >= ?"
        params.append(args.since)
    if args.until:
        sql += " AND release_date <= ?"
        params.append(args.until)
    sql += " ORDER BY name"
    rows = [dict(r) for r in conn.execute(sql, params)]
    # Load contracts for each collection
    for r in rows:
        r['contracts'] = [dict(c) for c in conn.execute(
            "SELECT address, chain, is_primary FROM contracts WHERE collection_id=? ORDER BY is_primary DESC, chain",
            (r['id'],))]
    conn.close()
    return rows

def query_opensea(args):
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM opensea_candidates WHERE 1=1"
    params = []
    if args.query:
        sql += " AND (slug LIKE ? OR name LIKE ? OR contract LIKE ? OR vrm_url LIKE ?)"
        p = f"%{args.query}%"
        params.extend([p, p, p, p])
    if args.status:
        sql += " AND status = ?"
        params.append(args.status)
    if args.nft_type:
        sql += " AND nft_type = ?"
        params.append(args.nft_type)
    if args.mint:
        sql += " AND mint_status = ?"
        params.append(args.mint)
    sql += " ORDER BY slug"
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()
    return rows

def query_avatars(args):
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    sql = "SELECT a.*, c.name as collection_name FROM avatars a LEFT JOIN collections c ON a.collection_id = c.id WHERE 1=1"
    params = []
    if args.query:
        sql += " AND (a.name LIKE ? OR a.collection_id LIKE ? OR a.description LIKE ? OR a.model_file_url LIKE ?)"
        p = f"%{args.query}%"
        params.extend([p, p, p, p])
    sql += " ORDER BY a.collection_id, a.name"
    if not args.all_avatars:
        sql += " LIMIT 50"
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()
    return rows

def show_stats():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    s = {
        'collections': conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0],
        'avatars': conn.execute("SELECT COUNT(*) FROM avatars").fetchone()[0],
        'opensea_candidates': conn.execute("SELECT COUNT(*) FROM opensea_candidates").fetchone()[0],
    }
    print("VRM Index Statistics")
    print("=" * 40)
    print(f"  Collections:       {s['collections']}")
    print(f"  Avatars:           {s['avatars']}")
    print(f"  OpenSea candidates:{s['opensea_candidates']}")
    print()
    print("  By tier:")
    for r in conn.execute("SELECT tier, COUNT(*) as n FROM collections GROUP BY tier ORDER BY n DESC"):
        print(f"    {r['tier'] or '?':12s} {r['n']}")
    print()
    print("  By chain:")
    for r in conn.execute("SELECT chain, COUNT(*) as n FROM collections GROUP BY chain ORDER BY n DESC"):
        print(f"    {r['chain'] or '?':12s} {r['n']}")
    print()
    print("  By license:")
    for r in conn.execute("SELECT license_category, COUNT(*) as n FROM collections GROUP BY license_category ORDER BY n DESC"):
        print(f"    {r['license_category'] or '?':12s} {r['n']}")
    print()
    print("  OpenSea by status:")
    for r in conn.execute("SELECT status, COUNT(*) as n FROM opensea_candidates GROUP BY status ORDER BY n DESC"):
        print(f"    {r['status'] or '?':12s} {r['n']}")
    conn.close()

def print_collections(rows, as_json=False):
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("No collections found.")
        return
    print(f"{'Collection':<35} {'Tier':<4} {'Released':<11} {'Chain':<10} {'Lic':<5} {'URL':<4} {'Soc':<5} {'Total':<18} {'Type':<14} {'Avatars':<8} {'Contracts'}")
    print("-" * 172)
    for c in rows:
        lic = {'green': '🟢', 'yellow': '🟡', 'red': '🔴'}.get(c['license_category'], '?')
        us = c.get('url_status', '')
        url_icon = {'alive': '✓', 'dead': '✗', 'error': '?'}.get(us, '—')
        ds = c.get('discord_status', '')
        dc_icon = {'alive': '✓', 'dead': '✗', 'rate_limited': '⏳', 'error': '?'}.get(ds, '—')
        tw = c.get('twitter_username', '')
        tw_icon = '𝕏' if tw else '—'
        soc = f"{dc_icon}{tw_icon}"
        ms = c.get('mint_status', '')
        ms_icon = {'capped': '🔒', 'likely_capped': '🔒~', 'ongoing': '🟢', 'no_max_supply': '❓', 'unknown': '❓'}.get(ms, '—')
        total = c.get('total_supply')
        total_str = f"{total:,}" if total else '?'
        max_s = c.get('max_supply')
        supply_str = f"{ms_icon} {total_str}" + (f"/{max_s:,}" if max_s else "") + (f" ({c['mint_progress']}%)" if ms == 'ongoing' and c.get('mint_progress') else "")
        nft_type = c.get('nft_type', 'unknown') or 'unknown'
        nft_icons = {'generative':'🎲', '1of1_series':'🎨', '1of1_art':'🖼', 'numbered':'🔢', 'no_traits':'∅', 'mixed':'🔀', 'unknown':'❓'}
        nft_str = f"{nft_icons.get(nft_type,'?')} {nft_type}"
        contracts = c.get('contracts', [])
        if contracts:
            ct_str = ' '.join(f"{ct['address'][:8]}..({ct['chain'][:3]})" for ct in contracts[:3])
            if len(contracts) > 3: ct_str += f" +{len(contracts)-3}"
        else:
            ct_str = (c.get('contract') or '—')[:12]
        print(f"{c['name'][:34]:<35} {c['tier'] or '?':<4} {c.get('release_date') or '?':<11} {c['chain'] or '?':<10} {lic:<5} {url_icon:<4} {soc:<5} {supply_str:<18} {nft_str:<14} {c['avatar_count'] or '-':<8} {ct_str}")
    print(f"\n{len(rows)} collection(s)")

def print_opensea(rows, as_json=False):
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("No OpenSea candidates found.")
        return
    print(f"{'Slug':<40} {'Name':<30} {'Released':<11} {'Chain':<10} {'VRM':<10} {'URL':<4} {'Soc':<5} {'Members':<8} {'Contract'}")
    print("-" * 142)
    for c in rows:
        us = c.get('url_status', '')
        url_icon = {'alive': '✓', 'dead': '✗', 'error': '?'}.get(us, '—')
        ds = c.get('discord_status', '')
        dc_icon = {'alive': '✓', 'dead': '✗', 'rate_limited': '⏳', 'error': '?'}.get(ds, '—')
        tw = c.get('twitter_username', '')
        tw_icon = '𝕏' if tw else '—'
        soc = f"{dc_icon}{tw_icon}"
        members = f"{c.get('discord_members',0):,}" if ds == 'alive' else '—'
        ct = (c.get('contract') or '—')[:12]
        print(f"{c['slug'][:39]:<40} {c['name'][:29]:<30} {c.get('release_date') or '?':<11} {c['chain'] or '?':<10} {c['status'] or '?':<10} {url_icon:<4} {soc:<5} {members:<8} {ct}")
    print(f"\n{len(rows)} candidate(s)")

def print_avatars(rows, as_json=False):
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("No avatars found.")
        return
    print(f"{'Name':<25} {'Collection':<20} {'Format':<8} {'Model URL'}")
    print("-" * 100)
    for a in rows:
        url = a['model_file_url'] or ''
        print(f"{a['name'][:24]:<25} {a['collection_id'][:19]:<20} {a['format'] or '?':<8} {url[:50]}")
    print(f"\n{len(rows)} avatar(s)")

def main():
    p = argparse.ArgumentParser(description="Search the VRM collection index")
    p.add_argument("query", nargs="?", help="Search query (matches name, contract, slug, etc.)")
    p.add_argument("--license", choices=["green", "yellow", "red", "unknown"], help="Filter by license category")
    p.add_argument("--chain", help="Filter by chain (ethereum, base, optimism, polygon, shape, solana, arweave, multi)")
    p.add_argument("--tier", help="Filter by tier (A, B, C, arweave, infra, not_vrm)")
    p.add_argument("--contract", help="Search by contract address prefix")
    p.add_argument("--url-status", choices=["alive", "dead", "error"], help="Filter by OpenSea URL status")
    p.add_argument("--discord", choices=["alive", "dead", "none"], help="Filter by Discord invite status")
    p.add_argument("--mint", choices=["capped", "likely_capped", "ongoing", "no_max_supply"], help="Filter by mint/supply status")
    p.add_argument("--nft-type", choices=["generative", "1of1_series", "1of1_art", "numbered", "no_traits", "mixed"], help="Filter by NFT type")
    p.add_argument("--wayback", action="store_true", help="Only show collections with Wayback Machine archives")
    p.add_argument("--since", help="Only collections released on or after this date (YYYY-MM-DD)")
    p.add_argument("--until", help="Only collections released on or before this date (YYYY-MM-DD)")
    p.add_argument("--opensea", action="store_true", help="Search OpenSea candidates instead of collections")
    p.add_argument("--status", help="Filter OpenSea candidates by status (vrm, no_vrm, mentions, not_checked)")
    p.add_argument("--avatars", action="store_true", help="Search avatars instead of collections")
    p.add_argument("--all-avatars", action="store_true", help="Show all avatars (default: limit 50)")
    p.add_argument("--stats", action="store_true", help="Show index statistics")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    args = p.parse_args()

    if not DB.exists():
        print(f"Database not found: {DB}", file=sys.stderr)
        print("Run: python3 build_index.py", file=sys.stderr)
        sys.exit(1)

    if args.stats:
        show_stats()
        return

    if args.opensea:
        rows = query_opensea(args)
        print_opensea(rows, args.json)
    elif args.avatars:
        rows = query_avatars(args)
        print_avatars(rows, args.json)
    else:
        rows = query_collections(args)
        print_collections(rows, args.json)

if __name__ == "__main__":
    main()
