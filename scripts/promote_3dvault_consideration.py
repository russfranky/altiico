#!/usr/bin/env python3
"""Materialize evidence-backed 3dvault named projects into catalog consideration rows.

This is collection-level promotion, not binary VRM promotion. It makes named,
identity-resolved 3D avatar collections visible in the catalog while preserving
the distinction between public GLB evidence, holder-gated VRM delivery, and
unverified native VRM claims.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE / "data" / "vrm_index.db"
DEFAULT_REPORT = BASE / "data" / "3dvault_named_project_discovery.json"

POLICY = {
    "clonex": {
        "tier": "C",
        "delivery": "3d_to_vrm",
        "note": "Holder-gated official 3D files; official RTFKT tooling supports VRM export. Native per-token VRM not observed in sampled NFT metadata.",
        "project_url": "https://clonex.rtfkt.com/",
        "license_category": "yellow",
        "vrm_license": "Holder-gated RTFKT 3D files; separate license terms",
        "commercial_use": "Holder terms",
        "allowed_user": "Token holder",
        "vrm_param": None,
        "vrm_url_pattern": None,
    },
    "thewynlambo": {
        "tier": "C",
        "delivery": "3d_confirmed",
        "note": "OpenSea describes the collection as full 3D NFTs. Native VRM delivery remains under verification.",
        "project_url": "https://www.immadegen.com/",
        "license_category": "unknown",
        "vrm_license": "",
        "commercial_use": "unknown",
        "allowed_user": "unknown",
        "vrm_param": None,
        "vrm_url_pattern": None,
    },
    "visitors-of-imma-degen": {
        "tier": "C",
        "delivery": "3d_avatar_confirmed",
        "note": "OpenSea states every VOID includes a metaverse-ready avatar/3D model. Native VRM delivery remains under verification.",
        "project_url": "https://www.immadegen.com/",
        "license_category": "unknown",
        "vrm_license": "",
        "commercial_use": "unknown",
        "allowed_user": "unknown",
        "vrm_param": None,
        "vrm_url_pattern": None,
    },
    "voyagers-of-imma-degen": {
        "tier": "B",
        "delivery": "holder_vrm_confirmed",
        "note": "OpenSea states all PFPs include VRM, GLB and FBX via the 3D Vault. 38 sampled public model URLs fetched as valid GLB 2.0 but not VRM; VRM is a separate holder-gated/private vault delivery path.",
        "project_url": "https://voltz.me/en/vault",
        "license_category": "yellow",
        "vrm_license": "Full commercial IP rights to holders stated by collection; VRM files holder-gated",
        "commercial_use": "Allow for holder",
        "allowed_user": "Token holder",
        "vrm_param": "holder-gated-vault",
        "vrm_url_pattern": "https://voltz.me/en/vault",
    },
}


def ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(collections)")}
    for name, spec in {
        "avatar_delivery_status": "TEXT",
        "avatar_delivery_evidence": "TEXT",
    }.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE collections ADD COLUMN {name} {spec}")


def cid(contract: str) -> str:
    return f"research-{contract[:8].lower()}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = ap.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    by_slug = {row.get("slug"): row for row in report.get("collections", []) if isinstance(row, dict)}
    conn = sqlite3.connect(args.db)
    ensure_columns(conn)
    promoted = []

    for slug, policy in POLICY.items():
        row = by_slug.get(slug)
        if not row or not row.get("contract"):
            continue
        contract = row["contract"].lower()
        collection_id = cid(contract)
        evidence = {
            "source": "3dvault+OpenSea targeted discovery",
            "observedAt": report.get("generatedAt"),
            "slug": slug,
            "nftsSampled": row.get("nfts_sampled", 0),
            "metadataDocuments": row.get("metadata_documents", 0),
            "modelCandidates": len(row.get("model_candidates") or []),
            "validatedVrms": len(row.get("validated_vrms") or []),
            "rejectedModelStatuses": sorted({str(v.get("status")) for v in row.get("rejected_model_candidates") or []}),
            "note": policy["note"],
        }
        conn.execute(
            """INSERT INTO collections
            (id,name,tier,chain,contract,opensea_slug,vrm_param,vrm_url_pattern,
             license_category,vrm_license,commercial_use,allowed_user,redistribution,
             creator,description,notes,source,image_url,banner_image_url,project_url,
             avatar_delivery_status,avatar_delivery_evidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name,tier=excluded.tier,chain=excluded.chain,contract=excluded.contract,
              opensea_slug=excluded.opensea_slug,vrm_param=excluded.vrm_param,
              vrm_url_pattern=excluded.vrm_url_pattern,license_category=excluded.license_category,
              vrm_license=excluded.vrm_license,commercial_use=excluded.commercial_use,
              allowed_user=excluded.allowed_user,description=excluded.description,notes=excluded.notes,
              source=excluded.source,image_url=excluded.image_url,banner_image_url=excluded.banner_image_url,
              project_url=excluded.project_url,avatar_delivery_status=excluded.avatar_delivery_status,
              avatar_delivery_evidence=excluded.avatar_delivery_evidence""",
            (
                collection_id, row.get("name") or slug, policy["tier"], "ethereum", contract, slug,
                policy["vrm_param"], policy["vrm_url_pattern"], policy["license_category"],
                policy["vrm_license"], policy["commercial_use"], policy["allowed_user"], "unknown",
                "", row.get("description") or "", policy["note"], "3dvault-targeted",
                row.get("image_url") or "", row.get("banner_image_url") or "", policy["project_url"],
                policy["delivery"], json.dumps(evidence, separators=(",", ":")),
            ),
        )
        conn.execute(
            """INSERT OR REPLACE INTO contracts(collection_id,address,chain,token_standard,is_primary)
               VALUES (?,?,?,?,1)""",
            (collection_id, contract, "ethereum", "ERC-721"),
        )
        promoted.append({
            "id": collection_id,
            "slug": slug,
            "name": row.get("name"),
            "contract": contract,
            "delivery": policy["delivery"],
            "modelCandidates": len(row.get("model_candidates") or []),
        })

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
    holder = conn.execute("SELECT COUNT(*) FROM collections WHERE avatar_delivery_status='holder_vrm_confirmed'").fetchone()[0]
    conn.close()
    print(json.dumps({"materialized": promoted, "catalogCollections": total, "holderVrmConfirmed": holder}, indent=2))


if __name__ == "__main__":
    main()
