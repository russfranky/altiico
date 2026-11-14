#!/usr/bin/env python3
"""Cross-check runner: executes inside GitHub Actions in russfranky/altiico,
where BITQUERY_API_KEY, ETHERSCAN_API_KEY and MORALIS_API_KEY exist as
Actions secrets. Reads research/crosscheck/crosscheck_inputs.json, writes
JSONL results into research/crosscheck/results/. Every stage is defensive:
one failing source never blocks the others. No key is ever printed."""
import os, sys, json, time, urllib.request, urllib.parse, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)
inputs = json.load(open(os.path.join(HERE, "crosscheck_inputs.json")))
contracts = inputs["contracts"]
by_slug = {c["slug"]: c["contract"] for c in contracts}
summary = {"stages": {}}

def http(url, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("User-Agent", "altiico-crosscheck/1.0")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def load_done(path):
    done = set()
    if os.path.exists(path):
        for line in open(path):
            try: done.add(json.loads(line)["slug"])
            except Exception: pass
    return done

# ---------- Stage 1: Etherscan contract creation ----------
def stage_etherscan():
    key = os.environ.get("ETHERSCAN_API_KEY", "")
    out = os.path.join(RES, "etherscan_creation.jsonl")
    if not key:
        return {"skipped": "no key"}
    done = load_done(out)
    todo = [c for c in contracts if c["slug"] not in done]
    addr2slug = {}
    for c in todo: addr2slug[c["contract"].lower()] = c["slug"]
    addrs = [c["contract"] for c in todo]
    creations = {}
    for i in range(0, len(addrs), 5):
        batch = addrs[i:i+5]
        q = urllib.parse.urlencode({"chainid": "1", "module": "contract",
            "action": "getcontractcreation", "contractaddresses": ",".join(batch), "apikey": key})
        try:
            d = http(f"https://api.etherscan.io/v2/api?{q}")
            for r in (d.get("result") or []):
                creations[r["contractAddress"].lower()] = r
        except Exception as e:
            print("etherscan batch error:", str(e)[:100], flush=True)
        time.sleep(0.25)
    blocks = {}
    fh = open(out, "a")
    n = 0
    for addr, slug in addr2slug.items():
        r = creations.get(addr)
        rec = {"slug": slug, "contract": addr}
        if r:
            rec["creator"] = r.get("contractCreator")
            rec["creation_tx"] = r.get("txHash")
            tx = r.get("txHash")
            try:
                if tx and tx not in blocks:
                    q = urllib.parse.urlencode({"chainid": "1", "module": "proxy",
                        "action": "eth_getTransactionByHash", "txhash": tx, "apikey": key})
                    t = http(f"https://api.etherscan.io/v2/api?{q}")
                    bn = (t.get("result") or {}).get("blockNumber")
                    blocks[tx] = int(bn, 16) if bn else None
                    time.sleep(0.25)
                rec["creation_block"] = blocks.get(tx)
                if rec["creation_block"]:
                    q = urllib.parse.urlencode({"chainid": "1", "module": "block",
                        "action": "getblockrewardbyblockno", "blockno": rec["creation_block"], "apikey": key})
                    b = http(f"https://api.etherscan.io/v2/api?{q}")
                    ts = (b.get("result") or {}).get("timeStamp")
                    if ts:
                        import datetime
                        rec["creation_date"] = datetime.datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
                    time.sleep(0.25)
            except Exception as e:
                rec["date_error"] = str(e)[:80]
        fh.write(json.dumps(rec) + "\n"); n += 1
    fh.close()
    return {"rows": n}

# ---------- Stage 2: Moralis trades for quiet collections ----------
def stage_moralis():
    key = os.environ.get("MORALIS_API_KEY", "")
    out = os.path.join(RES, "moralis_trades.jsonl")
    if not key:
        return {"skipped": "no key"}
    done = load_done(out)
    fh = open(out, "a")
    n = 0; stopped = None
    for slug in inputs["quiet_slugs"]:
        if slug in done: continue
        addr = by_slug.get(slug)
        if not addr: continue
        rec = {"slug": slug, "contract": addr}
        try:
            d = http(f"https://deep-index.moralis.io/api/v2.2/nft/{addr}/trades?chain=eth&limit=100",
                     headers={"X-API-Key": key, "accept": "application/json"})
            res = d.get("result") or []
            rec["n_trades_page"] = len(res)
            rec["total"] = d.get("total")
            mkts = {}
            latest = None
            for t in res:
                m = t.get("exchange") or t.get("marketplace") or "unknown"
                mkts[m] = mkts.get(m, 0) + 1
                bt = t.get("block_timestamp")
                if bt and (latest is None or bt > latest): latest = bt
            rec["marketplaces"] = mkts
            rec["latest_trade"] = latest
        except urllib.error.HTTPError as e:
            rec["error"] = f"HTTP {e.code}"
            if e.code in (401, 403):
                stopped = f"moralis stopped: HTTP {e.code}"
                fh.write(json.dumps(rec) + "\n"); n += 1
                break
        except Exception as e:
            rec["error"] = str(e)[:100]
        fh.write(json.dumps(rec) + "\n"); n += 1
        time.sleep(0.12)
    fh.close()
    return {"rows": n, "stopped": stopped}

# ---------- Stage 3: Bitquery latest transfer + post-2025 activity ----------
BQ_QUERY = """query($c: String!) {
  EVM(network: eth, dataset: archive) {
    latest: Transfers(where: {Transfer: {Currency: {SmartContract: {is: $c}}}},
      limit: {count: 1}, orderBy: {descending: Block_Number}) { Block { Date } }
    recent: Transfers(where: {Transfer: {Currency: {SmartContract: {is: $c}}},
      Block: {Date: {after: "2024-12-31"}}}, limit: {count: 1}) { Block { Date } }
  }
}"""
def stage_bitquery():
    key = os.environ.get("BITQUERY_API_KEY", "")
    out = os.path.join(RES, "bitquery_transfers.jsonl")
    if not key:
        return {"skipped": "no key"}
    done = load_done(out)
    fh = open(out, "a")
    n = 0
    for slug in inputs["bitquery_slugs"]:
        if slug in done: continue
        addr = by_slug.get(slug)
        if not addr: continue
        rec = {"slug": slug, "contract": addr}
        try:
            body = json.dumps({"query": BQ_QUERY, "variables": {"c": addr}}).encode()
            d = http("https://streaming.bitquery.io/graphql",
                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, data=body)
            if d.get("errors"):
                rec["error"] = json.dumps(d["errors"])[:200]
            else:
                evm = (d.get("data") or {}).get("EVM") or {}
                lat = evm.get("latest") or []
                recn = evm.get("recent") or []
                rec["latest_transfer_date"] = (lat[0].get("Block") or {}).get("Date") if lat else None
                rec["has_transfers_2025plus"] = bool(recn)
        except Exception as e:
            rec["error"] = str(e)[:150]
        fh.write(json.dumps(rec) + "\n"); n += 1
        time.sleep(0.15)
    fh.close()
    return {"rows": n}

for name, fn in [("etherscan", stage_etherscan), ("moralis", stage_moralis), ("bitquery", stage_bitquery)]:
    try:
        summary["stages"][name] = fn()
    except Exception as e:
        summary["stages"][name] = {"fatal": str(e)[:200]}
    print(name, summary["stages"][name], flush=True)
json.dump(summary, open(os.path.join(RES, "summary.json"), "w"), indent=1)
print("crosscheck run complete")
