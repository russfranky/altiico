#!/usr/bin/env python3
"""Deep-inspect named collections recovered from 3dvault's escaped locale data."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts.opensea_client import OpenSeaClient
from scripts.discover_opensea_candidates import _inspect_collection

DEFAULT_SLUGS = (
    "clonex",
    "chimperschronicles",
    "immadegen-quantum-cube",
    "thewynlambo",
    "visitors-of-imma-degen",
    "voyagers-of-imma-degen",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run(args: argparse.Namespace) -> dict[str, Any]:
    slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
    client = OpenSeaClient(max_concurrency=2)
    leads = []
    try:
        for slug in slugs:
            lead = {
                "slug": slug,
                "name": slug,
                "description": "",
                "contract": "",
                "chains": [],
                "external_url": "",
                "image_url": "",
                "banner_image_url": "",
                "nfts_sampled": 0,
                "metadata_documents": 0,
                "metadata_fetch_errors": 0,
                "model_candidates": [],
                "validated_vrms": [],
                "rejected_model_candidates": [],
                "errors": [],
            }
            try:
                detail = await client.get_collection(slug)
                collection = detail.get("collection") if isinstance(detail, dict) and isinstance(detail.get("collection"), dict) else detail
                if isinstance(collection, dict):
                    lead["name"] = str(collection.get("name") or slug)
                    lead["description"] = str(collection.get("description") or "")
                    lead["external_url"] = str(collection.get("project_url") or collection.get("external_url") or "")
                    lead["image_url"] = str(collection.get("image_url") or "")
                    lead["banner_image_url"] = str(collection.get("banner_image_url") or "")
                    contracts = collection.get("contracts") or []
                    if isinstance(contracts, list):
                        for c in contracts:
                            if not isinstance(c, dict):
                                continue
                            addr = str(c.get("address") or "").lower()
                            chain = str(c.get("chain") or "")
                            if addr.startswith("0x") and not lead["contract"]:
                                lead["contract"] = addr
                            if chain and chain not in lead["chains"]:
                                lead["chains"].append(chain)
            except Exception as exc:
                lead["errors"].append(f"collection_detail: {type(exc).__name__}: {exc}"[:500])
            leads.append(lead)

        inspect_args = SimpleNamespace(sample=args.sample, timeout=args.timeout)
        gate = asyncio.Semaphore(args.collection_concurrency)
        await asyncio.gather(*(
            _inspect_collection(lead, client, inspect_args, gate, i, len(leads))
            for i, lead in enumerate(leads, 1)
        ))
    finally:
        await client.close()

    status_counts: dict[str, int] = {}
    for lead in leads:
        for row in lead["rejected_model_candidates"]:
            status = str(row.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

    out = {
        "schema": "3dvault-named-project-discovery-v1",
        "generatedAt": now(),
        "source": "3dvault recovered OpenSea collection identities",
        "policy": "lead-only until binary GLB 2.0 + VRM/VRMC_vrm validation passes",
        "summary": {
            "collectionsInspected": len(leads),
            "nftsSampled": sum(x["nfts_sampled"] for x in leads),
            "metadataDocuments": sum(x["metadata_documents"] for x in leads),
            "modelCandidates": sum(len(x["model_candidates"]) for x in leads),
            "validatedVrms": sum(len(x["validated_vrms"]) for x in leads),
            "collectionsWithValidatedVrms": sum(bool(x["validated_vrms"]) for x in leads),
            "rejectedModelCandidates": sum(len(x["rejected_model_candidates"]) for x in leads),
            "validationStatuses": status_counts,
        },
        "collections": leads,
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", default=",".join(DEFAULT_SLUGS))
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--timeout", type=float, default=12)
    ap.add_argument("--collection-concurrency", type=int, default=2)
    ap.add_argument("--output", type=Path, default=Path("data/3dvault_named_project_discovery.json"))
    args = ap.parse_args()
    out = asyncio.run(run(args))
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    for c in out["collections"]:
        print(json.dumps({"slug": c["slug"], "name": c["name"], "contract": c["contract"], "nfts": c["nfts_sampled"], "modelCandidates": len(c["model_candidates"]), "validatedVrms": len(c["validated_vrms"]), "external": c["external_url"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
