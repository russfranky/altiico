#!/usr/bin/env python3
"""Re-check no_vrm results by fetching metadata from public IPFS gateway."""
import json, re, time, sys, urllib.request

def fetch(url, timeout=20):
    if not url: return ""
    # Replace private pinata with public ipfs.io
    url = url.replace("opensea-private.mypinata.cloud/ipfs/", "ipfs.io/ipfs/")
    url = url.replace("mypinata.cloud/ipfs/", "ipfs.io/ipfs/")
    if url.startswith("ipfs://"):
        url = "https://ipfs.io/ipfs/" + url[7:]
    elif url.startswith("arweave://"):
        url = "https://arweave.net/" + url[9:]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 vrm-scraper/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return ""

def check_meta(meta):
    """Check metadata text for VRM references. Returns (param, url) or None."""
    if not meta: return None
    # Standard JSON fields
    for pattern in [
        r'"(vrm_url)"\s*:\s*"([^"]+)"',
        r'"(vrm)"\s*:\s*"([^"]+)"',
        r'"(avatar_url)"\s*:\s*"([^"]+)"',
        r'"(asset)"\s*:\s*"([^"]+\.vrm[^"]*)"',
        r'"(model_vrm)"\s*:\s*"([^"]+)"',
        r'"(model/vrm)"\s*:\s*"([^"]+)"',
        r'"(files)"\s*:\s*\[([^\]]*\.vrm[^\]]*)\]',
    ]:
        m = re.search(pattern, meta, re.I)
        if m:
            return (m.group(1), m.group(2))
    # Any .vrm URL anywhere
    m = re.search(r'((?:https?|ipfs|arweave)://[^\s"\']+\.vrm[^\s"\']*)', meta, re.I)
    if m:
        return ("_url", m.group(1))
    # VRM mentioned in description
    if re.search(r'\bVRM\b', meta):
        return ("mentions", "")
    return None

d = json.load(open("os_scrape/vrm_check_results.json"))
no_vrm = d["no_vrm"]
print(f"Re-checking {len(no_vrm)} no_vrm collections with public IPFS gateway...", file=sys.stderr)

new_vrm = []
new_mentions = []
still_no = []

for i, e in enumerate(no_vrm):
    meta_url = e.get("metadata_url", "")
    if not meta_url or meta_url.startswith("data:"):
        still_no.append(e)
        continue
    meta = fetch(meta_url)
    result = check_meta(meta)
    if result:
        param, vrm_url = result
        e["vrm_param"] = param
        e["vrm_url"] = vrm_url
        if param == "mentions":
            new_mentions.append(e)
            print(f"  ~ mentions: {e['slug']} ({e['name']})", file=sys.stderr)
        else:
            new_vrm.append(e)
            print(f"  ✓ VRM: {e['slug']} ({e['name']}) — {param}={vrm_url[:80]}", file=sys.stderr)
    else:
        still_no.append(e)
    if i % 20 == 0:
        print(f"  [{i}/{len(no_vrm)}]", file=sys.stderr)
    time.sleep(0.3)

# Merge results
d["vrm"].extend(new_vrm)
d["mentions"].extend(new_mentions)
d["no_vrm"] = still_no

json.dump(d, open("os_scrape/vrm_check_results_v2.json", "w"), indent=2)
print(f"\nDone. New VRM: {len(new_vrm)}, new mentions: {len(new_mentions)}, still no: {len(still_no)}", file=sys.stderr)
print(f"Total VRM: {len(d['vrm'])}, total mentions: {len(d['mentions'])}", file=sys.stderr)
