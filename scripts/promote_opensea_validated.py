#!/usr/bin/env python3
"""Promote named OpenSea NFT discoveries that already have binary VRM proof.

Discovery may return 1/1s, untitled dumps, and mixed art editions. This script
only inserts a catalog row when:

- the OpenSea slug is a real name (not untitled-collection-N / junk)
- at least MIN_UNIQUE_VRMS distinct content hashes validated as VRM
- those hashes come from at least MIN_UNIQUE_VRMS distinct token ids

Shared storefront contracts are never stored as the collection identity.
The OpenSea slug is the id. Dedicated contracts are stored normally.

Does not invent descriptions, socials, licenses, or supply.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discover_opensea_nfts import (
    JUNK_COLLECTION_SLUGS,
    UNTITLED_COLLECTION_RE,
    unique_validations,
)
from scripts.resolve_opensea_collections import SHARED_STOREFRONT_CONTRACTS

BASE = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE / "data" / "vrm_index.db"
DEFAULT_REPORT = BASE / "data" / "opensea_nft_discovery_report.json"

MIN_UNIQUE_VRMS = 3
TITLE_HASH_RE = re.compile(r"\s*#\s*\d+\b.*$", re.I)
TITLE_VRM_SUFFIX_RE = re.compile(
    r"\s*(?:3D\s+Avatar\s+Character\s*)?\.vrm\s*$",
    re.I,
)


def is_named_slug(slug: str) -> bool:
    value = (slug or "").strip().lower()
    if not value or value in JUNK_COLLECTION_SLUGS:
        return False
    if UNTITLED_COLLECTION_RE.match(value):
        return False
    return True


def collection_title(names: list[str], slug: str) -> str:
    cleaned: list[str] = []
    for raw in names:
        text = TITLE_HASH_RE.sub("", str(raw or "")).strip()
        text = TITLE_VRM_SUFFIX_RE.sub("", text).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            cleaned.append(text)
    if cleaned and all(item == cleaned[0] for item in cleaned):
        return cleaned[0]
    return slug.replace("-", " ").title()


def group_validated(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for nft in report.get("nfts") or []:
        if not isinstance(nft, dict):
            continue
        slug = str(nft.get("collection") or "").strip()
        if not is_named_slug(slug):
            continue
        validations = unique_validations(
            [row for row in (nft.get("validated_vrms") or []) if isinstance(row, dict)]
        )
        if not validations:
            continue
        rec = groups.setdefault(
            slug.lower(),
            {
                "slug": slug.lower(),
                "chain": nft.get("chain"),
                "contract": (nft.get("contract") or "").lower(),
                "names": [],
                "token_ids": [],
                "validations": [],
                "image_url": "",
            },
        )
        rec["names"].append(nft.get("name") or "")
        rec["token_ids"].append(str(nft.get("token_id") or ""))
        rec["validations"].extend(validations)
        payload = nft.get("search_payload") or {}
        if not rec["image_url"] and isinstance(payload, dict):
            rec["image_url"] = payload.get("image_url") or ""
        if not rec["chain"]:
            rec["chain"] = nft.get("chain")
    for rec in groups.values():
        rec["validations"] = unique_validations(rec["validations"])
        rec["token_ids"] = [tid for tid in rec["token_ids"] if tid]
    return groups


def is_admissible(rec: dict[str, Any], min_unique: int = MIN_UNIQUE_VRMS) -> bool:
    unique_vrms = rec.get("validations") or []
    unique_tokens = {tid for tid in rec.get("token_ids") or [] if tid}
    return len(unique_vrms) >= min_unique and len(unique_tokens) >= min_unique


def pick_sample(validations: list[dict[str, Any]]) -> dict[str, Any]:
    def size(row: dict[str, Any]) -> int:
        try:
            return int(row.get("bytes") or 0)
        except (TypeError, ValueError):
            return 0

    ranked = sorted(validations, key=lambda row: (size(row) or 10**12, row.get("canonical_url") or ""))
    return ranked[0]


def https_url(row: dict[str, Any]) -> str:
    transport = str(row.get("transport_url") or "")
    canonical = str(row.get("canonical_url") or "")
    if transport.startswith("https://"):
        return transport
    if canonical.startswith("https://"):
        return canonical
    return transport or canonical


def stored_contract(rec: dict[str, Any]) -> str:
    address = (rec.get("contract") or "").lower()
    if address in SHARED_STOREFRONT_CONTRACTS:
        return ""
    return address


def ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(collections)")}
    for name, spec in {
        "vrm_reachable": "INTEGER",
        "vrm_check_status": "TEXT",
        "vrm_check_bytes": "INTEGER",
        "vrm_check_url": "TEXT",
        "vrm_checked_at": "TEXT",
        "vrm_url_https": "TEXT",
    }.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE collections ADD COLUMN {name} {spec}")


def upsert_collection(
    conn: sqlite3.Connection,
    rec: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    slug = rec["slug"]
    sample = pick_sample(rec["validations"])
    url = https_url(sample)
    contract = stored_contract(rec)
    name = collection_title(rec["names"], slug)
    note = (
        f"{len(rec['validations'])} distinct token files binary-validated as VRM "
        f"{sample.get('vrm_spec') or '0.x'} from OpenSea NFT search. "
        + (
            "Identity is the OpenSea slug; the shared storefront contract is not a collection id."
            if not contract
            else "Dedicated contract observed on the validated tokens."
        )
    )
    evidence = {
        "source": "opensea-nft-discovery",
        "observedAt": observed_at,
        "slug": slug,
        "uniqueValidatedVrms": len(rec["validations"]),
        "tokensWithValidatedVrms": len({tid for tid in rec["token_ids"] if tid}),
        "sharedStorefront": not bool(contract),
        "sampleSha256": sample.get("content_sha256") or sample.get("sha256"),
        "sampleBytes": sample.get("bytes"),
    }
    conn.execute(
        """INSERT INTO collections (
            id,name,tier,chain,contract,opensea_slug,vrm_param,vrm_url_pattern,
            license_category,vrm_license,commercial_use,allowed_user,redistribution,
            creator,description,notes,source,image_url,banner_image_url,project_url,
            vrm_url_https,vrm_reachable,vrm_check_status,vrm_check_bytes,vrm_check_url,vrm_checked_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            tier=excluded.tier,
            chain=excluded.chain,
            contract=excluded.contract,
            opensea_slug=excluded.opensea_slug,
            vrm_param=excluded.vrm_param,
            notes=excluded.notes,
            source=excluded.source,
            image_url=COALESCE(NULLIF(excluded.image_url,''), collections.image_url),
            vrm_url_https=excluded.vrm_url_https,
            vrm_reachable=excluded.vrm_reachable,
            vrm_check_status=excluded.vrm_check_status,
            vrm_check_bytes=excluded.vrm_check_bytes,
            vrm_check_url=excluded.vrm_check_url,
            vrm_checked_at=excluded.vrm_checked_at
        """,
        (
            slug,
            name,
            "A",
            rec.get("chain") or "polygon",
            contract,
            slug,
            sample.get("field") or "animation_url",
            None,
            "unknown",
            "",
            "unknown",
            "unknown",
            "unknown",
            "",
            "",
            note,
            "opensea-nft-discovery",
            rec.get("image_url") or "",
            "",
            f"https://opensea.io/collection/{slug}",
            url,
            1,
            "ok_vrm",
            sample.get("bytes"),
            url,
            observed_at,
        ),
    )
    if contract:
        conn.execute(
            "INSERT OR REPLACE INTO contracts(collection_id,address,chain,token_standard,is_primary) VALUES (?,?,?,?,1)",
            (slug, contract, rec.get("chain") or "ethereum", "ERC-721"),
        )
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_candidates'"
    ).fetchone():
        for validation in rec["validations"]:
            sha = validation.get("content_sha256") or validation.get("sha256") or ""
            candidate_id = f"osnft-{slug}-{str(sha)[:16]}"
            conn.execute(
                """INSERT INTO promotion_candidates
                (candidate_id,collection_id,chain,contract,token_id,name,model_url,canonical_url,source,observed_at,validation_status,vrm_spec,sha256,byte_length,promotion_state,reason,evidence_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                  collection_id=excluded.collection_id,
                  observed_at=excluded.observed_at,
                  validation_status=excluded.validation_status,
                  promotion_state=excluded.promotion_state,
                  reason=excluded.reason
                """,
                (
                    candidate_id,
                    slug,
                    rec.get("chain"),
                    rec.get("contract"),
                    validation.get("token_id"),
                    name,
                    https_url(validation),
                    validation.get("canonical_url"),
                    "opensea_nft_discovery_report.json",
                    observed_at,
                    validation.get("status") or "valid_vrm",
                    validation.get("vrm_spec"),
                    sha,
                    validation.get("bytes"),
                    "ready_for_reconciliation",
                    "binary VRM proof complete; eligible for canonical reconciliation",
                    json.dumps(evidence, separators=(",", ":")),
                ),
            )
    return {
        "id": slug,
        "name": name,
        "uniqueValidatedVrms": len(rec["validations"]),
        "sharedStorefront": not bool(contract),
        "sampleUrl": url,
    }


def promote(report: dict[str, Any], conn: sqlite3.Connection, min_unique: int = MIN_UNIQUE_VRMS) -> dict[str, Any]:
    ensure_columns(conn)
    observed_at = str(report.get("generated_at") or report.get("generatedAt") or "")
    admitted = []
    skipped = []
    for slug, rec in sorted(group_validated(report).items()):
        if not is_admissible(rec, min_unique=min_unique):
            skipped.append(
                {
                    "slug": slug,
                    "uniqueValidatedVrms": len(rec["validations"]),
                    "tokens": len({tid for tid in rec["token_ids"] if tid}),
                    "reason": "below-admission-bar",
                }
            )
            continue
        admitted.append(upsert_collection(conn, rec, observed_at))
    return {
        "admitted": admitted,
        "skipped": skipped,
        "catalogCollections": conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--min-unique-vrms", type=int, default=MIN_UNIQUE_VRMS)
    args = ap.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    conn = sqlite3.connect(args.db)
    summary = promote(report, conn, min_unique=args.min_unique_vrms)
    conn.commit()
    conn.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
