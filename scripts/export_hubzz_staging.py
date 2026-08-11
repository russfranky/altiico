#!/usr/bin/env python3
"""Export a conservative Hubzz pre-alpha staging bundle.

The catalog is evidence and source inventory. Hubzz owns optimization, R2 upload,
canonical served URLs, and publication. This exporter therefore emits:

* canonical set records with status=staged and listed=false
* source-avatar sidecars containing original VRM candidates
* an explicit deferred queue with machine-readable blockers

A set is stageable only when at least one VRM binary has been validated, either
at collection level or on an individual avatar row. Unknown licensing is a
warning, not a rights grant. Unsupported ownership chains are deferred instead
of being silently coerced to null.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

SCHEMA_NAME = "hubzz-prealpha-staging-v1"
SCHEMA_VERSION = 1
PREALPHA_CHAINS = {"ethereum", "zora", "polygon", "base", "optimism", "arbitrum"}
STORAGE_ONLY_CHAINS = {"ipfs", "arweave"}
VALID_AVATAR_STATUSES = {"ok_vrm", "ok_glb"}
OWNER_EXCLUSIONS = {"declined", "excluded", "remove", "removed", "handled"}


@dataclass(frozen=True)
class Evidence:
    canonical_url: str
    transport_url: str
    vrm_spec: str | None
    total_length: int | None
    validated_at: str | None
    token_id: str | None
    source: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def slug_safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "set"


def public_url(value: Any) -> str | None:
    text = norm(value)
    if not text or any(ch.isspace() for ch in text):
        return None
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    return text if parts.scheme in {"http", "https"} and parts.netloc else None


def token_id_from(value: Any) -> str | None:
    text = norm(value)
    if not text:
        return None
    if text.isdigit():
        return text
    match = re.search(r"(?:^|[/#:_-])(\d+)(?:\.[A-Za-z0-9]+)?$", text)
    return match.group(1) if match else None


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def license_label(row: sqlite3.Row) -> str | None:
    raw = (norm(row["vrm_license"]) if "vrm_license" in row.keys() else None) or ""
    compact = raw.upper().replace(" ", "").replace("-", "").replace("_", "")
    if compact.startswith("CC0") or "PUBLICDOMAIN" in compact:
        return "CC0"
    for key, label in (
        ("CCBYNCND", "CC-BY-NC-ND"),
        ("CCBYNCSA", "CC-BY-NC-SA"),
        ("CCBYNC", "CC-BY-NC"),
        ("CCBYSA", "CC-BY-SA"),
        ("CCBYND", "CC-BY-ND"),
        ("CCBY", "CC-BY"),
    ):
        if compact.startswith(key):
            return label
    if "REDISTRIBUTIONPROHIBITED" in compact or "ALLRIGHTSRESERVED" in compact:
        return "All Rights Reserved"
    return raw or None


def purchase_gated(row: sqlite3.Row) -> bool | None:
    category = ((norm(row["license_category"]) if "license_category" in row.keys() else None) or "").lower()
    allowed = ((norm(row["allowed_user"]) if "allowed_user" in row.keys() else None) or "").lower()
    redistribution = ((norm(row["redistribution"]) if "redistribution" in row.keys() else None) or "").lower()
    label = license_label(row)
    if category == "red" or allowed == "holder" or redistribution == "prohibited":
        return True
    if label == "All Rights Reserved":
        return True
    if category == "green" or label in {"CC0", "CC-BY", "CC-BY-SA"}:
        return False
    return None


def map_chain(row: sqlite3.Row) -> tuple[str | None, str | None]:
    chain = ((norm(row["chain"]) if "chain" in row.keys() else None) or "").lower()
    if chain in PREALPHA_CHAINS:
        return chain, None
    if not chain or chain in STORAGE_ONLY_CHAINS:
        return None, None
    return None, f"unsupported_chain:{chain}"


def source_url(row: sqlite3.Row, evidence: Evidence | None) -> str | None:
    if evidence:
        return evidence.canonical_url or evidence.transport_url
    for key in ("vrm_url_https", "vrm_check_url", "vrm_url_pattern"):
        if key in row.keys() and norm(row[key]):
            return norm(row[key])
    return None


def storage_provider(row: sqlite3.Row, evidence: Evidence | None) -> str:
    candidate = (source_url(row, evidence) or "").lower()
    chain = ((norm(row["chain"]) if "chain" in row.keys() else None) or "").lower()
    if candidate.startswith("ipfs://") or "/ipfs/" in candidate or ".ipfs." in candidate:
        return "ipfs"
    if candidate.startswith(("ar://", "arweave://")) or "arweave.net" in candidate or chain == "arweave":
        return "arweave"
    if candidate:
        return "self-host"
    if ("sample_metadata_url" in row.keys() and norm(row["sample_metadata_url"])) or (
        "vrm_param" in row.keys() and norm(row["vrm_param"])
    ):
        return "contract-metadata"
    return "self-host"


def ingest_source(row: sqlite3.Row) -> str:
    source = ((norm(row["source"]) if "source" in row.keys() else None) or "").lower()
    contract = norm(row["contract"]) if "contract" in row.keys() else None
    if contract:
        return "ethereum"
    if any(word in source for word in ("opensource", "open-source", "toxsam", "osa")):
        return "opensource"
    return "manual"


def latest_evidence(conn: sqlite3.Connection, collection_id: str, row: sqlite3.Row) -> Evidence | None:
    if table_exists(conn, "crawl_observations") and table_exists(conn, "crawl_bindings"):
        result = conn.execute(
            """
            SELECT o.value_json, o.observed_at, b.seed_source, t.payload_json
            FROM crawl_observations o
            JOIN crawl_tasks t ON t.id=o.task_id
            JOIN crawl_bindings b ON b.task_id=t.id
            WHERE o.predicate='valid_vrm' AND b.collection_id=?
            ORDER BY o.id DESC
            LIMIT 1
            """,
            (collection_id,),
        ).fetchone()
        if result:
            value = json.loads(result["value_json"])
            payload = json.loads(result["payload_json"])
            canonical = norm(value.get("canonical_url"))
            transport = norm(value.get("transport_url"))
            if canonical or transport:
                return Evidence(
                    canonical_url=canonical or transport or "",
                    transport_url=transport or canonical or "",
                    vrm_spec=norm(value.get("vrm_spec")),
                    total_length=value.get("total_length") if isinstance(value.get("total_length"), int) else None,
                    validated_at=norm(result["observed_at"]),
                    token_id=token_id_from(payload.get("token_id")),
                    source=norm(result["seed_source"]) or "recursive-crawler",
                )

    status = norm(row["vrm_check_status"]) if "vrm_check_status" in row.keys() else None
    url = norm(row["vrm_url_https"]) if "vrm_url_https" in row.keys() else None
    if status == "ok_vrm" and url:
        return Evidence(
            canonical_url=url,
            transport_url=url,
            vrm_spec=None,
            total_length=row["vrm_check_bytes"] if "vrm_check_bytes" in row.keys() and isinstance(row["vrm_check_bytes"], int) else None,
            validated_at=norm(row["vrm_checked_at"]) if "vrm_checked_at" in row.keys() else None,
            token_id=token_id_from(row["sample_metadata_url"]) if "sample_metadata_url" in row.keys() else None,
            source="collection-validation",
        )
    return None


def avatar_rows(conn: sqlite3.Connection, collection_id: str) -> list[dict[str, Any]]:
    cols = columns(conn, "avatars")
    if not {"id", "collection_id", "model_file_url"} <= cols:
        return []
    wanted = [
        name for name in (
            "id", "name", "model_file_url", "thumbnail_url", "metadata_json",
            "reachable", "check_status", "checked_at", "check_http"
        ) if name in cols
    ]
    rows = conn.execute(
        f"SELECT {', '.join(wanted)} FROM avatars WHERE collection_id=? ORDER BY id",
        (collection_id,),
    ).fetchall()
    output: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in rows:
        url = norm(item["model_file_url"])
        if not url or url in seen_urls:
            continue
        reachable = ("reachable" in item.keys() and item["reachable"] == 1) or (
            "check_status" in item.keys() and norm(item["check_status"]) in VALID_AVATAR_STATUSES
        )
        if not reachable:
            continue
        seen_urls.add(url)
        token_id = token_id_from(item["id"])
        metadata: dict[str, Any] = {}
        if "metadata_json" in item.keys() and norm(item["metadata_json"]):
            try:
                parsed = json.loads(item["metadata_json"])
                metadata = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                metadata = {}
        for key in ("token_id", "tokenId", "identifier"):
            token_id = token_id or token_id_from(metadata.get(key))
        output.append(
            {
                "id": str(item["id"]),
                "tokenId": token_id,
                "name": norm(item["name"]) if "name" in item.keys() else None,
                "originalSourceUrl": url,
                "thumbnailUrl": public_url(item["thumbnail_url"]) if "thumbnail_url" in item.keys() else None,
                "validated": True,
                "checkedAt": norm(item["checked_at"]) if "checked_at" in item.keys() else None,
                "checkStatus": norm(item["check_status"]) if "check_status" in item.keys() else "reachable",
            }
        )
    return output


def known_avatar_count(conn: sqlite3.Connection, collection_id: str) -> int:
    if not table_exists(conn, "avatars"):
        return 0
    return int(conn.execute("SELECT COUNT(*) FROM avatars WHERE collection_id=?", (collection_id,)).fetchone()[0])


def primary_contract(conn: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    if table_exists(conn, "contracts"):
        found = conn.execute(
            """
            SELECT address FROM contracts WHERE collection_id=?
            ORDER BY is_primary DESC, rowid ASC LIMIT 1
            """,
            (row["id"],),
        ).fetchone()
        if found and norm(found["address"]):
            return norm(found["address"])
    return norm(row["contract"]) if "contract" in row.keys() else None


def total_mints(row: sqlite3.Row) -> int | None:
    for key in ("total_supply", "max_supply", "avatar_count"):
        if key not in row.keys():
            continue
        value = row[key]
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def owner_excluded(row: sqlite3.Row) -> bool:
    if "owner_decision" not in row.keys():
        return False
    value = ((norm(row["owner_decision"]) or "").lower())
    return value in OWNER_EXCLUSIONS


def make_sample_avatar(row: sqlite3.Row, evidence: Evidence) -> dict[str, Any]:
    token_id = evidence.token_id
    sample_name = norm(row["sample_nft_name"]) if "sample_nft_name" in row.keys() else None
    avatar_id = token_id or "sample"
    return {
        "id": avatar_id,
        "tokenId": token_id,
        "name": sample_name or f"{row['name']} sample",
        "originalSourceUrl": evidence.canonical_url or evidence.transport_url,
        "transportUrl": evidence.transport_url,
        "thumbnailUrl": public_url(row["sample_nft_image"]) if "sample_nft_image" in row.keys() else None,
        "validated": True,
        "checkedAt": evidence.validated_at,
        "checkStatus": "ok_vrm",
        "vrmSpec": evidence.vrm_spec,
        "fileSizeOriginal": evidence.total_length,
    }


def stage_record(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    generated_at: str,
    assets_root: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    collection_id = str(row["id"])
    evidence = latest_evidence(conn, collection_id, row)
    avatars = avatar_rows(conn, collection_id)
    known = known_avatar_count(conn, collection_id)
    chain, chain_blocker = map_chain(row)
    contract = primary_contract(conn, row)
    blockers: list[str] = []
    warnings: list[str] = []

    if owner_excluded(row):
        blockers.append("owner_excluded")
    if "is_nsfw" in row.keys() and row["is_nsfw"] == 1:
        blockers.append("nsfw_requires_review")
    if chain_blocker:
        blockers.append(chain_blocker)
    if chain and not contract:
        blockers.append("missing_contract")
    if not avatars and evidence is None:
        blockers.append("no_validated_vrm")
    if not avatars and evidence is not None:
        warnings.append("sample_only")
    if known and 0 < len(avatars) < known:
        warnings.append("partial_avatar_inventory")
    if purchase_gated(row) is None:
        warnings.append("license_requires_review")
    if not public_url(row["banner_image_url"]) if "banner_image_url" in row.keys() else True:
        warnings.append("missing_banner")
    if not public_url(row["image_url"]) if "image_url" in row.keys() else True:
        warnings.append("missing_pfp")

    facts = {
        "slug": collection_id,
        "name": row["name"],
        "tier": norm(row["tier"]) if "tier" in row.keys() else None,
        "chain": norm(row["chain"]) if "chain" in row.keys() else None,
        "contract": contract,
        "knownAvatars": known,
        "validatedSourceAvatars": len(avatars),
        "collectionVrmValidated": evidence is not None,
        "vrmCheckStatus": norm(row["vrm_check_status"]) if "vrm_check_status" in row.keys() else None,
    }
    deferred = {"slug": collection_id, "name": row["name"], "reasons": blockers, "warnings": warnings, "facts": facts}
    if blockers:
        return None, deferred

    if avatars:
        source_avatars = avatars
        stage_class = "bulk_ready" if known and len(avatars) == known else "partial_ready"
    else:
        assert evidence is not None
        source_avatars = [make_sample_avatar(row, evidence)]
        stage_class = "preview_ready"

    safe_slug = slug_safe(collection_id)
    asset_path = assets_root / f"{safe_slug}.json"
    asset_payload = {
        "schema": "hubzz-prealpha-source-avatars-v1",
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "setSlug": collection_id,
        "count": len(source_avatars),
        "avatars": source_avatars,
    }
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_text(json.dumps(asset_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    set_record = {
        "schemaVersion": 1,
        "slug": collection_id,
        "name": str(row["name"]),
        "description": norm(row["description"]) if "description" in row.keys() else None,
        "chain": chain,
        "contract": contract,
        "storageProvider": storage_provider(row, evidence),
        "ingestSource": ingest_source(row),
        "license": license_label(row),
        "author": norm(row["creator"]) if "creator" in row.keys() else None,
        "copyright": None,
        "mintDate": norm(row["release_date"]) if "release_date" in row.keys() else None,
        "totalMints": total_mints(row),
        "bannerUrl": public_url(row["banner_image_url"]) if "banner_image_url" in row.keys() else None,
        "pfpUrl": (public_url(row["image_url"]) if "image_url" in row.keys() else None)
        or (public_url(row["sample_nft_image"]) if "sample_nft_image" in row.keys() else None),
        "purchaseGated": purchase_gated(row),
        "listed": False,
        "status": "staged",
        "avatarCount": len(source_avatars),
    }
    coverage_total = total_mints(row) or known or len(source_avatars)
    entry = {
        "set": set_record,
        "stageClass": stage_class,
        "sourceAssets": {
            "path": f"hubzz-prealpha-source/{asset_path.name}",
            "count": len(source_avatars),
            "mode": "enumerated" if avatars else "validated_sample",
        },
        "coverage": {
            "knownAvatars": known,
            "validatedSourceAvatars": len(avatars),
            "catalogSupply": total_mints(row),
            "coverageRatio": round(len(source_avatars) / coverage_total, 6) if coverage_total else None,
        },
        "sampleEvidence": None if evidence is None else {
            "canonicalUrl": evidence.canonical_url,
            "transportUrl": evidence.transport_url,
            "vrmSpec": evidence.vrm_spec,
            "fileSizeOriginal": evidence.total_length,
            "validatedAt": evidence.validated_at,
            "tokenId": evidence.token_id,
            "source": evidence.source,
        },
        "warnings": warnings,
    }
    return entry, deferred


def load_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute("SELECT * FROM collections ORDER BY name").fetchall()


def build_bundle(conn: sqlite3.Connection, output_path: Path) -> dict[str, Any]:
    generated_at = utc_now()
    assets_root = output_path.parent / "hubzz-prealpha-source"
    assets_root.mkdir(parents=True, exist_ok=True)
    for stale in assets_root.glob("*.json"):
        stale.unlink()

    stageable: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    rows = load_rows(conn)
    for row in rows:
        entry, deferred_entry = stage_record(conn, row, generated_at, assets_root)
        if entry:
            stageable.append(entry)
        else:
            deferred.append(deferred_entry)

    stageable.sort(key=lambda item: (item["stageClass"], item["set"]["name"].lower()))
    deferred.sort(key=lambda item: item["name"].lower())
    summary = {
        "catalogSets": len(rows),
        "stageableSets": len(stageable),
        "bulkReadySets": sum(1 for item in stageable if item["stageClass"] == "bulk_ready"),
        "partialReadySets": sum(1 for item in stageable if item["stageClass"] == "partial_ready"),
        "previewReadySets": sum(1 for item in stageable if item["stageClass"] == "preview_ready"),
        "deferredSets": len(deferred),
        "sourceAvatars": sum(item["sourceAssets"]["count"] for item in stageable),
        "openLicenseSets": sum(1 for item in stageable if item["set"]["purchaseGated"] is False),
        "gatedSets": sum(1 for item in stageable if item["set"]["purchaseGated"] is True),
        "licenseReviewSets": sum(1 for item in stageable if item["set"]["purchaseGated"] is None),
    }
    return {
        "schema": SCHEMA_NAME,
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "source": {"repository": "russfranky/vrm-catalog", "database": "data/vrm_index.db"},
        "summary": summary,
        "sets": stageable,
        "deferred": deferred,
    }


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if bundle.get("schema") != SCHEMA_NAME or bundle.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("wrong staging schema or version")
    seen: set[str] = set()
    for index, item in enumerate(bundle.get("sets") or []):
        record = item.get("set") or {}
        slug = record.get("slug")
        prefix = f"sets[{index}]"
        if not slug or slug in seen:
            errors.append(f"{prefix}: missing or duplicate slug")
        seen.add(slug)
        if record.get("status") != "staged" or record.get("listed") is not False:
            errors.append(f"{prefix}: must be staged and unlisted")
        if item.get("stageClass") not in {"bulk_ready", "partial_ready", "preview_ready"}:
            errors.append(f"{prefix}: invalid stageClass")
        source = item.get("sourceAssets") or {}
        if not isinstance(source.get("count"), int) or source.get("count", 0) < 1:
            errors.append(f"{prefix}: no source avatars")
        if record.get("avatarCount") != source.get("count"):
            errors.append(f"{prefix}: avatar count mismatch")
        chain = record.get("chain")
        if chain is not None and chain not in PREALPHA_CHAINS:
            errors.append(f"{prefix}: unsupported chain leaked into stageable sets")
        if chain and not record.get("contract"):
            errors.append(f"{prefix}: mapped chain lacks contract")
    return errors


def write_markdown(bundle: dict[str, Any], path: Path) -> None:
    summary = bundle["summary"]
    lines = [
        "# Hubzz pre-alpha staging bundle",
        "",
        f"Generated at: `{bundle['generatedAt']}`",
        "",
        "## Summary",
        "",
        f"- Stageable sets: **{summary['stageableSets']}**",
        f"- Bulk-ready sets: **{summary['bulkReadySets']}**",
        f"- Partial-inventory sets: **{summary['partialReadySets']}**",
        f"- Preview-ready sets: **{summary['previewReadySets']}**",
        f"- Validated source avatars: **{summary['sourceAvatars']}**",
        f"- Deferred sets: **{summary['deferredSets']}**",
        "",
        "## Stageable sets",
        "",
        "| Set | Class | Avatars | Chain | License gate | Warnings |",
        "|---|---|---:|---|---|---|",
    ]
    for item in bundle["sets"]:
        record = item["set"]
        gate = "open" if record["purchaseGated"] is False else "gated" if record["purchaseGated"] is True else "review"
        lines.append(
            f"| `{record['slug']}` | {item['stageClass']} | {record['avatarCount']} | "
            f"{record['chain'] or 'none'} | {gate} | {', '.join(item['warnings']) or 'none'} |"
        )
    reason_counts: dict[str, int] = {}
    for item in bundle["deferred"]:
        for reason in item["reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    lines.extend(["", "## Deferred queue", "", "| Reason | Sets |", "|---|---:|"])
    for reason, count in sorted(reason_counts.items(), key=lambda pair: (-pair[1], pair[0])):
        lines.append(f"| `{reason}` | {count} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Export Hubzz pre-alpha staging candidates")
    parser.add_argument("--db", default=str(root / "data" / "vrm_index.db"))
    parser.add_argument("--output", default=str(root / "static" / "data" / "hubzz-prealpha-staging.json"))
    parser.add_argument("--report", default=str(root / "docs" / "hubzz-prealpha-staging.md"))
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"error: database not found: {db_path}", file=sys.stderr)
        return 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        bundle = build_bundle(conn, output)
    finally:
        conn.close()
    errors = validate_bundle(bundle)
    if args.validate and errors:
        for error in errors:
            print(f"validation error: {error}", file=sys.stderr)
        return 1
    output.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(bundle, Path(args.report))
    summary = bundle["summary"]
    print(
        f"wrote {output}: {summary['stageableSets']} stageable sets, "
        f"{summary['sourceAvatars']} source avatars, {summary['deferredSets']} deferred",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
