#!/usr/bin/env python3
"""Combine OpenSea/Moralis consensus with Etherscan explorer evidence."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
CROSS=ROOT/"data/source_consensus.json"
ETH=ROOT/"data/etherscan_authority_report.json"
OUT=ROOT/"data/authoritative_consensus.json"

def now_iso(): return datetime.now(timezone.utc).isoformat()

def main():
    consensus=json.loads(CROSS.read_text())
    etherscan=json.loads(ETH.read_text())
    by_id={x.get("catalogId"):x for x in etherscan.get("collections",[]) if x.get("catalogId")}
    collections=[]; review=[]
    for item in consensus.get("collections",[]):
        cid=item.get("catalogId"); es=by_id.get(cid); conflicts=list(item.get("conflicts") or [])
        es_conflicts=(es or {}).get("conflicts") or []
        evidence=(es or {}).get("contractEvidence") or {}
        contract_corroborated=bool(evidence.get("creator") or evidence.get("verifiedSource") or evidence.get("creationTxHash"))
        record={**item,"etherscan":{
            "observedAt":(es or {}).get("observedAt"),
            "contractCorroborated":contract_corroborated,
            "verifiedSource":evidence.get("verifiedSource"),
            "contractName":evidence.get("contractName"),
            "proxy":evidence.get("proxy"),
            "implementation":evidence.get("implementation"),
            "creator":evidence.get("creator"),
            "creationTxHash":evidence.get("creationTxHash"),
            "creationBlock":evidence.get("creationBlock"),
            "tokenInfo":evidence.get("tokenInfo"),
            "abiSignals":evidence.get("abiSignals"),
            "errors":(es or {}).get("errors") or [],
            "conflicts":es_conflicts,
        },"authorityStatus":"explorer_corroborated" if contract_corroborated else "index_only_or_unavailable"}
        collections.append(record)
        if conflicts or es_conflicts or (es and es.get("errors")):
            review.append({"catalogId":cid,"name":item.get("name"),"chain":item.get("chain"),"contract":item.get("contract"),"sourceConflicts":conflicts,"etherscanConflicts":es_conflicts,"etherscanErrors":(es or {}).get("errors") or []})
    payload={"schema":"authoritative-catalog-consensus-v1","generatedAt":now_iso(),"policy":{"identity":"chain+contract are anchored by direct discovery/on-chain evidence; Etherscan contract/deployment evidence corroborates identity; OpenSea/Moralis indexes never silently override it","mutableFields":"preserve per-source timestamps and conflicts","vrm":"only binary GLB 2.0 + VRM/VRMC_vrm validation proves VRM","market":"market values are mutable and source-specific"},"summary":{"collections":len(collections),"explorerCorroborated":sum(x["authorityStatus"]=="explorer_corroborated" for x in collections),"reviewItems":len(review),"etherscanConflicts":sum(len(x["etherscanConflicts"]) for x in review)},"collections":collections,"reviewQueue":review}
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n"); print(json.dumps(payload["summary"],indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
