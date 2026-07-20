#!/usr/bin/env python3
"""For each OpenSea collection slug, fetch one NFT, fetch its metadata, check for VRM."""
import json, os, time, sys, urllib.request, urllib.parse, re

API = "https://api.opensea.io/api/v2"
KEY = open(os.path.expanduser("~/.opensea/api_key")).read().strip()

def get(url):
    req = urllib.request.Request(url, headers={"X-API-KEY": KEY, "User-Agent": "vrm-scraper/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  rate limited, sleeping 30s...", file=sys.stderr)
                time.sleep(30)
                continue
            if e.code == 404:
                return None
            if e.code in (400, 500, 502, 503):
                time.sleep(2)
                continue
            raise
        except Exception as e:
            time.sleep(2)
    return None

def fetch_url(url):
    if not url: return ""
    if url.startswith("ipfs://"):
        url = "https://ipfs.io/ipfs/" + url[7:]
    elif url.startswith("arweave://"):
        url = "https://arweave.net/" + url[9:]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vrm-scraper/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return ""

def check_collection(slug):
    """Returns (has_vrm, sample_nft_name, metadata_url, vrm_param, vrm_url) or None if no NFTs."""
    data = get(f"{API}/collection/{slug}/nfts?limit=1")
    if not data or not data.get("nfts"):
        return None
    nft = data["nfts"][0]
    name = nft.get("name", "")
    metadata_url = nft.get("metadata_url") or ""
    # Also check NFT fields directly
    nft_str = json.dumps(nft)
    vrm_hits = re.findall(r'[a-z_]*vrm[a-z_]*["\s:=]+["\']?([^"\',\s]+\.vrm[^"\',\s]*)', nft_str, re.I)
    if not vrm_hits:
        # Check animation_url, image_url, etc for .vrm
        for fld in ["animation_url", "image_url", "external_url", "metadata_url"]:
            v = nft.get(fld, "") or ""
            if ".vrm" in v.lower():
                vrm_hits = [v]
                break
    if vrm_hits:
        return (True, name, metadata_url, "nft_field", vrm_hits[0])
    # Fetch metadata
    if metadata_url:
        meta = fetch_url(metadata_url)
        if meta:
            # Find VRM references
            hits = re.findall(r'"([a-z_]*vrm[a-z_]*)"\s*:\s*"([^"]+\.vrm[^"]*)"', meta, re.I)
            if not hits:
                # Also check for .vrm URLs in any field
                hits = re.findall(r'"([a-z_]*vrm[a-z_]*)"\s*:\s*([^"]+)', meta, re.I)
                hits = [(k,v.strip('"')) for k,v in hits if ".vrm" in v.lower()]
            if not hits:
                # Broader: any .vrm URL anywhere
                m = re.search(r'(https?://[^\s"\']+\.vrm[^\s"\']*)|ipfs://[^\s"\']+\.vrm[^\s"\']*|arweave://[^\s"\']+\.vrm', meta, re.I)
                if m:
                    hits = [("_url", m.group(0))]
            if hits:
                return (True, name, metadata_url, hits[0][0], hits[0][1])
            # Check if metadata mentions VRM in description
            if re.search(r'\bVRM\b|\.vrm\b', meta):
                return ("mentions", name, metadata_url, "description", "")
    return (False, name, metadata_url, "", "")

def main():
    slugs = []
    import glob
    for f in sorted(glob.glob("data/os_scrape/q_*.json")) + sorted(glob.glob("data/os_scrape/search_*.json")):
        try:
            d = json.load(open(f))
        except: continue
        for r in d.get("results", []):
            if r.get("type") == "collection":
                c = r.get("collection") or {}
                slug = c.get("collection")
                if slug:
                    slugs.append((slug, c.get("name","?")))
    # dedupe
    seen = {}
    for slug, name in slugs:
        if slug not in seen:
            seen[slug] = name
    slugs = list(seen.items())
    print(f"Checking {len(slugs)} collections...", file=sys.stderr)

    results = {"vrm": [], "mentions": [], "no_vrm": [], "error": []}
    for i, (slug, name) in enumerate(slugs):
        if i % 10 == 0:
            print(f"  [{i}/{len(slugs)}] {slug}", file=sys.stderr)
        r = check_collection(slug)
        if r is None:
            results["error"].append((slug, name, "no nfts"))
            continue
        has_vrm, nft_name, meta_url, param, vrm_url = r
        entry = {"slug": slug, "name": name, "sample_nft": nft_name, "metadata_url": meta_url, "vrm_param": param, "vrm_url": vrm_url}
        if has_vrm is True:
            results["vrm"].append(entry)
            print(f"  ✓ VRM: {slug} ({name}) — {param}={vrm_url[:80]}", file=sys.stderr)
        elif has_vrm == "mentions":
            results["mentions"].append(entry)
            print(f"  ~ mentions VRM: {slug} ({name})", file=sys.stderr)
        else:
            results["no_vrm"].append(entry)
        time.sleep(0.8)  # respect rate limit (60/min)
    json.dump(results, open("data/os_scrape/vrm_check_results.json","w"), indent=2)
    print(f"\nDone. VRM: {len(results['vrm'])}, mentions: {len(results['mentions'])}, no_vrm: {len(results['no_vrm'])}, error: {len(results['error'])}", file=sys.stderr)

if __name__ == "__main__":
    main()
