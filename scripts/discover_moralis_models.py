#!/usr/bin/env python3
"""High-recall model discovery from Moralis NFT metadata.

Moralis does not classify VRM/GLB as supported image/audio/video media. We use
`media_items=true`, raw/normalized metadata, token_uri and unsupported_media as
lead signals only. Candidates still require the catalog binary validator before
promotion.
"""
from __future__ import annotations
import argparse, asyncio, json, re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.moralis_client import CHAIN_MAP, MoralisClient  # noqa:E402

MODEL_RE=re.compile(r"(?:ipfs://|https?://|ar://)[^\s\"'<>]+?\.(?:vrm|glb|gltf|fbx|usdz)(?:\?[^\s\"'<>]*)?", re.I)
KEYWORDS=("vrm","glb","gltf","model","avatar","animation_url","3d")

def now_iso(): return datetime.now(timezone.utc).isoformat()
def text(v): return str(v or "").strip()

def walk(value: Any, path: str="$", depth: int=0):
    if depth>10: return
    if isinstance(value,dict):
        for k,v in value.items(): yield from walk(v,f"{path}.{k}",depth+1)
    elif isinstance(value,list):
        for i,v in enumerate(value): yield from walk(v,f"{path}[{i}]",depth+1)
    elif isinstance(value,str):
        yield path,value
        s=value.strip()
        if s.startswith(("{","[")):
            try: yield from walk(json.loads(s),path+".$json",depth+1)
            except json.JSONDecodeError: pass

def inspect_nft(nft: dict[str,Any]):
    hits=[]; unsupported=False; keyword_paths=[]
    for path,value in walk(nft):
        lower=value.lower()
        if "unsupported_media" in lower: unsupported=True
        if any(k in path.lower() or k in lower for k in KEYWORDS): keyword_paths.append({"path":path,"value":value[:500]})
        for m in MODEL_RE.finditer(value): hits.append({"path":path,"url":m.group(0).rstrip(".,;)")})
    dedup=[]; seen=set()
    for h in hits:
        key=(h["path"],h["url"])
        if key not in seen: seen.add(key); dedup.append(h)
    return {"unsupportedMedia":unsupported,"modelCandidates":dedup,"keywordSignals":keyword_paths[:20]}

async def run(args):
    conn=sqlite3.connect(args.db); conn.row_factory=sqlite3.Row
    rows=conn.execute("SELECT id,name,chain,contract FROM collections ORDER BY name").fetchall()
    rows=[r for r in rows if text(r["chain"]).lower() in CHAIN_MAP and text(r["contract"]).startswith("0x")]
    sem=asyncio.Semaphore(args.collection_concurrency)
    async with MoralisClient(max_concurrency=args.concurrency) as client:
        async def one(row):
            async with sem:
                try: data=await client.collection_nfts(row["chain"],row["contract"],limit=args.tokens)
                except Exception as exc: return {"catalogId":row["id"],"name":row["name"],"chain":row["chain"],"contract":row["contract"],"error":str(exc)[:500],"nfts":[]}
                out=[]
                for nft in (data.get("result") or [])[:args.tokens]:
                    if not isinstance(nft,dict): continue
                    sig=inspect_nft(nft)
                    if sig["unsupportedMedia"] or sig["modelCandidates"]:
                        out.append({"tokenId":text(nft.get("token_id")),"tokenUri":nft.get("token_uri"),**sig})
                return {"catalogId":row["id"],"name":row["name"],"chain":row["chain"],"contract":row["contract"],"error":None,"nfts":out}
        collections=await asyncio.gather(*(one(r) for r in rows))
    candidates=[(c,n) for c in collections for n in c["nfts"]]
    return {"schema":"moralis-model-discovery-v1","generatedAt":now_iso(),"policy":"lead-only; .vrm/.glb and unsupported_media are not VRM proof","summary":{"collectionsInspected":len(collections),"collectionsWithErrors":sum(bool(c["error"]) for c in collections),"nftsWithSignals":len(candidates),"modelCandidates":sum(len(n["modelCandidates"]) for _,n in candidates),"unsupportedMediaNfts":sum(bool(n["unsupportedMedia"]) for _,n in candidates)},"collections":collections}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--db",default=str(ROOT/"data/vrm_index.db")); p.add_argument("--output",default=str(ROOT/"data/moralis_model_discovery.json")); p.add_argument("--tokens",type=int,default=25); p.add_argument("--concurrency",type=int,default=3); p.add_argument("--collection-concurrency",type=int,default=3); a=p.parse_args(); r=asyncio.run(run(a)); Path(a.output).write_text(json.dumps(r,indent=2,ensure_ascii=False)+"\n"); print(json.dumps(r["summary"],indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
