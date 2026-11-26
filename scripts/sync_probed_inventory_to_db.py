#!/usr/bin/env python3
"""Sync verified binary VRM probe proofs into vrm_index.db cleanly and idempotently."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from scripts.crawler.uri import canonicalize_uri  # noqa: E402

DEFAULT_DB = BASE / "data" / "vrm_index.db"
DEFAULT_INVENTORY = BASE / "static" / "data" / "avatar-inventory.json"
DEFAULT_PROBE = BASE / "data" / "avatar_inventory_probe.json"
DEFAULT_PROBED_NEW = BASE / "data" / "probed_new_sets.json"

INVENTORY_SYNC_TARGETS = ("boomboxheads-v2", "chuddie", "meebits", "dickbuttverse")

TUBBY_CONTRACT = "0xca7ca7bcc765f77339be2d648ba53ce9c8a262bd"
TUBBY_DESC = "20,000-item CC0 collection with verified public community VRM conversions."


def canonicalize(url: str) -> str:
    raw = url.strip()
    m = re.match(r"^https?://[^/]+/ipfs/(.+)$", raw, re.I)
    if m:
        return f"ipfs://{m.group(1).lstrip('/')}"
    try:
        return canonicalize_uri(raw)
    except Exception:
        return raw


def extract_token_id(url: str) -> str | None:
    path = url.split("?", 1)[0].split("#", 1)[0]
    m = re.search(r"/(\d+)/\1[^/]*\.vrm$", path, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(?:^|[/#:_-])(\d+)(?:\.[A-Za-z0-9]+)?$", path)
    if m:
        return m.group(1)
    m = re.search(r"/(\d+)[^/]*$", path)
    return m.group(1) if m else None


def stem_from_url(url: str) -> str:
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    name = path.rsplit("/", 1)[-1]
    return re.sub(r"\.vrm$", "", name, flags=re.I) or "avatar"


def upsert_vrm_metadata(
    conn: sqlite3.Connection,
    *,
    source_url: str,
    extracted_at: str,
    extractor_version: str,
    vrm_spec: str,
    raw_meta: dict[str, Any] | None = None,
    content_length: int | None = None,
    content_sha256: str | None = None,
    json_chunk_sha256: str | None = None,
    observed_content_length: int | None = None,
    transport_url: str | None = None,
) -> None:
    raw_json = json.dumps(raw_meta, ensure_ascii=False, separators=(",", ":")) if raw_meta else None
    conn.execute(
        """
        INSERT INTO vrm_metadata (
            source_url, extracted_at, extractor_version, vrm_spec, vrm_meta_json,
            parse_error, content_length, content_sha256, json_chunk_sha256,
            observed_content_length, transport_url
        )
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
        ON CONFLICT(source_url) DO UPDATE SET
            extracted_at=excluded.extracted_at,
            extractor_version=excluded.extractor_version,
            vrm_spec=excluded.vrm_spec,
            vrm_meta_json=COALESCE(excluded.vrm_meta_json, vrm_metadata.vrm_meta_json),
            parse_error=NULL,
            content_length=COALESCE(excluded.content_length, vrm_metadata.content_length),
            content_sha256=COALESCE(excluded.content_sha256, vrm_metadata.content_sha256),
            json_chunk_sha256=COALESCE(excluded.json_chunk_sha256, vrm_metadata.json_chunk_sha256),
            observed_content_length=COALESCE(excluded.observed_content_length, vrm_metadata.observed_content_length),
            transport_url=COALESCE(excluded.transport_url, vrm_metadata.transport_url)
        """,
        (
            source_url,
            extracted_at,
            extractor_version,
            vrm_spec,
            raw_json,
            content_length,
            content_sha256,
            json_chunk_sha256,
            observed_content_length,
            transport_url,
        ),
    )


def upsert_avatar_with_vrm(
    conn: sqlite3.Connection,
    *,
    avatar_id: str,
    collection_id: str,
    name: str,
    canon_url: str,
    extracted_at: str,
    vrm_spec: str,
    thumbnail_url: str | None = None,
    token_id: str | None = None,
    raw_meta: dict[str, Any] | None = None,
    content_length: int | None = None,
    content_sha256: str | None = None,
    json_chunk_sha256: str | None = None,
    observed_content_length: int | None = None,
    transport_url: str | None = None,
) -> None:
    upsert_vrm_metadata(
        conn,
        source_url=canon_url,
        extracted_at=extracted_at,
        extractor_version="probe-sync-1",
        vrm_spec=vrm_spec,
        raw_meta=raw_meta,
        content_length=content_length,
        content_sha256=content_sha256,
        json_chunk_sha256=json_chunk_sha256,
        observed_content_length=observed_content_length,
        transport_url=transport_url,
    )
    meta_json = json.dumps({"token_id": token_id}, separators=(",", ":")) if token_id else None
    conn.execute(
        """
        INSERT INTO avatars (
            id, collection_id, name, model_file_url, format, thumbnail_url,
            is_public, metadata_json, reachable, check_status, check_http, checked_at
        )
        VALUES (?, ?, ?, ?, 'VRM', ?, 1, ?, 1, 'ok_vrm', 200, ?)
        ON CONFLICT(id) DO UPDATE SET
            collection_id=excluded.collection_id,
            name=excluded.name,
            model_file_url=excluded.model_file_url,
            format='VRM',
            thumbnail_url=COALESCE(excluded.thumbnail_url, avatars.thumbnail_url),
            is_public=1,
            metadata_json=COALESCE(excluded.metadata_json, avatars.metadata_json),
            reachable=1,
            check_status='ok_vrm',
            check_http=200,
            checked_at=excluded.checked_at
        """,
        (avatar_id, collection_id, name, canon_url, thumbnail_url, meta_json, extracted_at),
    )
    conn.execute(
        """
        INSERT INTO avatar_vrm (avatar_id, vrm_source_url)
        VALUES (?, ?)
        ON CONFLICT(avatar_id) DO UPDATE SET vrm_source_url=excluded.vrm_source_url
        """,
        (avatar_id, canon_url),
    )


def sync_inventory_probes(
    conn: sqlite3.Connection,
    inventory_path: Path,
    probe_path: Path,
    targets: tuple[str, ...] = INVENTORY_SYNC_TARGETS,
) -> dict[str, int]:
    if not inventory_path.exists() or not probe_path.exists():
        return {}
    inv = json.loads(inventory_path.read_text(encoding="utf-8"))
    probe_doc = json.loads(probe_path.read_text(encoding="utf-8"))
    checked_at = str(probe_doc.get("generatedAt") or "2026-11-26T00:00:00Z")

    probes_by_canon: dict[str, dict[str, Any]] = {}
    for p in probe_doc.get("probes") or []:
        if not isinstance(p, dict) or not p.get("validVrm") or not p.get("url"):
            continue
        probes_by_canon.setdefault(canonicalize(str(p["url"])), p)

    inv_by_id = {
        str(c.get("collection_id")): c
        for c in inv.get("collections") or []
        if isinstance(c, dict) and c.get("collection_id")
    }

    counts: dict[str, int] = {}
    for cid in targets:
        col_row = conn.execute("SELECT name, contract FROM collections WHERE id=?", (cid,)).fetchone()
        entry = inv_by_id.get(cid)
        if not col_row or not entry:
            continue
        col_name = str(col_row[0])
        contract = (col_row[1] or "").strip().lower()
        prefix = contract or cid

        seen_urls: set[str] = set()
        seen_ids: set[str] = set()
        inserted = 0
        for asset in entry.get("assets") or []:
            raw_url = str(asset.get("url") or "").strip() if isinstance(asset, dict) else str(asset).strip()
            if not raw_url:
                continue
            canon = canonicalize(raw_url)
            if canon in seen_urls:
                continue
            probe = probes_by_canon.get(canon)
            if not probe:
                continue
            seen_urls.add(canon)
            token_id = extract_token_id(canon)
            slug_part = token_id or stem_from_url(canon)
            avatar_id = f"{prefix}/{slug_part}"
            if avatar_id in seen_ids:
                avatar_id = f"{prefix}/{slug_part}-{inserted + 1}"
            seen_ids.add(avatar_id)
            label = f"{col_name} #{token_id}" if token_id else f"{col_name} ({stem_from_url(canon)})"
            upsert_avatar_with_vrm(
                conn,
                avatar_id=avatar_id,
                collection_id=cid,
                name=label,
                canon_url=canon,
                extracted_at=checked_at,
                vrm_spec=str(probe.get("vrmSpec") or "0.x"),
                token_id=token_id,
                content_length=probe.get("totalLength"),
                json_chunk_sha256=probe.get("jsonChunkSha256"),
                observed_content_length=probe.get("totalLength"),
                transport_url=probe.get("transportUrl"),
            )
            inserted += 1
        counts[cid] = inserted
    return counts


def ensure_tubby_cats(conn: sqlite3.Connection, probed: dict[str, Any], generated_at: str) -> int:
    tubby = probed.get("tubbyCats") or {}
    avatars = [a for a in tubby.get("avatars") or [] if a.get("valid")]
    if not avatars:
        return 0
    image_url = tubby.get("imageUrl") or ""
    banner_url = tubby.get("bannerImageUrl") or image_url
    sample_vrm = canonicalize(str(avatars[1]["url"] if len(avatars) > 1 else avatars[0]["url"]))
    sample_http = str(avatars[1].get("transportUrl") or avatars[1]["url"]) if len(avatars) > 1 else str(avatars[0]["url"])

    conn.execute(
        """
        INSERT INTO collections (
            id, name, tier, chain, contract, opensea_slug, license_category, vrm_license,
            commercial_use, allowed_user, redistribution, avatar_count, total_supply,
            description, short_description, source, image_url, banner_image_url,
            sample_nft_image, project_url, vrm_url_https, is_nsfw,
            vrm_reachable, vrm_check_status, vrm_check_http, vrm_check_bytes, vrm_check_url, vrm_checked_at
        )
        VALUES (?, 'Tubby Cats', 'B', 'ethereum', ?, 'tubby-cats-by-tubby-collective', 'green', 'CC0',
                'Allow', 'Everyone', 'Allow', ?, 20000, ?, ?, 'official+etherscan+curated+community-vrm-repository',
                ?, ?, ?, 'https://tubbycats.xyz/', ?, 0, 1, 'ok_vrm', 200, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            tier='B',
            chain='ethereum',
            contract=excluded.contract,
            opensea_slug=excluded.opensea_slug,
            license_category='green',
            vrm_license='CC0',
            commercial_use='Allow',
            allowed_user='Everyone',
            redistribution='Allow',
            avatar_count=excluded.avatar_count,
            total_supply=20000,
            image_url=COALESCE(NULLIF(excluded.image_url, ''), collections.image_url),
            banner_image_url=COALESCE(NULLIF(excluded.banner_image_url, ''), collections.banner_image_url),
            vrm_url_https=excluded.vrm_url_https,
            vrm_reachable=1,
            vrm_check_status='ok_vrm',
            vrm_check_http=200,
            vrm_check_bytes=excluded.vrm_check_bytes,
            vrm_check_url=excluded.vrm_check_url,
            vrm_checked_at=excluded.vrm_checked_at
        """,
        (
            "tubby-cats",
            TUBBY_CONTRACT,
            len(avatars),
            TUBBY_DESC,
            TUBBY_DESC,
            image_url,
            banner_url,
            image_url,
            sample_http,
            avatars[0].get("totalLength"),
            sample_vrm,
            generated_at,
        ),
    )
    conn.execute(
        """
        INSERT INTO contracts (collection_id, address, chain, token_standard, is_primary)
        VALUES ('tubby-cats', ?, 'ethereum', 'ERC-721', 1)
        ON CONFLICT(collection_id, address) DO UPDATE SET chain='ethereum', token_standard='ERC-721', is_primary=1
        """,
        (TUBBY_CONTRACT,),
    )
    conn.execute(
        """
        INSERT INTO license_dimensions (
            collection_id, raw_collection_terms, use_scope, commercial_scope, credit,
            redistribute_original, modify, redistribute_modified, corporate_use,
            terminates_on_transfer, color, reason_codes, confidence, conflict_flag, assessed_at
        )
        VALUES ('tubby-cats', ?, 'everyone', 'personal_profit', 'unnecessary', 1, 1, 1, 1, 0, 'green', '[]', 'collection', 0, ?)
        ON CONFLICT(collection_id) DO UPDATE SET
            use_scope='everyone',
            color='green',
            assessed_at=excluded.assessed_at
        """,
        (
            json.dumps(
                {
                    "vrm_license": "CC0",
                    "commercial_use": "Allow",
                    "allowed_user": "Everyone",
                    "redistribution": "Allow",
                    "license_category": "green",
                },
                separators=(",", ":"),
            ),
            generated_at,
        ),
    )
    for item in avatars:
        canon = canonicalize(str(item["url"]))
        token_id = extract_token_id(canon)
        stem = stem_from_url(canon)
        avatar_id = f"{TUBBY_CONTRACT}/{token_id or stem}"
        name = f"Tubby Cat #{token_id}" if token_id else f"Tubby Cat ({stem})"
        upsert_avatar_with_vrm(
            conn,
            avatar_id=avatar_id,
            collection_id="tubby-cats",
            name=name,
            canon_url=canon,
            extracted_at=generated_at,
            vrm_spec=str(item.get("vrmSpec") or "0.x"),
            thumbnail_url=image_url or None,
            token_id=token_id,
            raw_meta=item.get("rawMeta"),
            content_length=item.get("totalLength"),
            content_sha256=item.get("contentSha256"),
            json_chunk_sha256=item.get("jsonChunkSha256"),
            observed_content_length=item.get("observedLength"),
            transport_url=item.get("transportUrl"),
        )
    return len(avatars)


def sync_probed_new_sets(conn: sqlite3.Connection, probed_path: Path) -> dict[str, int]:
    if not probed_path.exists():
        return {}
    probed = json.loads(probed_path.read_text(encoding="utf-8"))
    generated_at = str(probed.get("generatedAt") or "2026-11-26T00:00:00Z")
    summary: dict[str, int] = {}

    summary["tubby-cats"] = ensure_tubby_cats(conn, probed, generated_at)

    # Avastars: preserve license_category='unknown', sync binary-validated Founder/Exclusive VRMs
    av_contract = conn.execute("SELECT contract FROM collections WHERE id='avastars'").fetchone()
    if av_contract and av_contract[0]:
        contract_addr = str(av_contract[0]).lower()
        av_count = 0
        for item in probed.get("avastars") or []:
            if not item.get("valid"):
                continue
            canon = canonicalize(str(item["canonicalUrl"]))
            tid = str(item.get("tokenId") or extract_token_id(canon) or "")
            if not tid:
                continue
            upsert_avatar_with_vrm(
                conn,
                avatar_id=f"{contract_addr}/{tid}",
                collection_id="avastars",
                name=f"Avastar #{tid}",
                canon_url=canon,
                extracted_at=generated_at,
                vrm_spec=str(item.get("vrmSpec") or "0.x"),
                token_id=tid,
                raw_meta=item.get("rawMeta"),
                content_length=item.get("totalLength"),
                content_sha256=item.get("contentSha256"),
                json_chunk_sha256=item.get("jsonChunkSha256"),
                observed_content_length=item.get("observedLength"),
                transport_url=item.get("transportUrl"),
            )
            av_count += 1
        summary["avastars"] = av_count

    # CryptoAvatars: record binary Arweave proof, keep chain='multi' untouched
    ca = probed.get("cryptoavatars")
    if isinstance(ca, dict) and ca.get("valid"):
        canon = canonicalize(str(ca.get("canonicalUrl") or ca["url"]))
        upsert_vrm_metadata(
            conn,
            source_url=canon,
            extracted_at=generated_at,
            extractor_version="probe-sync-1",
            vrm_spec=str(ca.get("vrmSpec") or "0.x"),
            raw_meta=ca.get("rawMeta"),
            content_length=ca.get("totalLength"),
            content_sha256=ca.get("contentSha256"),
            json_chunk_sha256=ca.get("jsonChunkSha256"),
            observed_content_length=ca.get("observedLength"),
            transport_url=ca.get("transportUrl"),
        )
        conn.execute(
            """
            UPDATE collections
            SET vrm_url_https=?, vrm_reachable=1, vrm_check_status='ok_vrm',
                vrm_check_http=200, vrm_check_bytes=?, vrm_check_url=?, vrm_checked_at=?
            WHERE id='cryptoavatars'
            """,
            (str(ca["url"]), ca.get("totalLength"), canon, generated_at),
        )
        summary["cryptoavatars"] = 1

    # NG86SHAPE (Polygon side): sync binary VRM 1.0 proof into avatars, keep license_category='unknown'
    ng = probed.get("ng86Polygon")
    ng_row = conn.execute("SELECT contract, image_url FROM collections WHERE id='neonglitch86-collection-polygon-side'").fetchone()
    if isinstance(ng, dict) and ng.get("valid") and ng_row and ng_row[0]:
        canon = canonicalize(str(ng.get("canonicalUrl") or ng["url"]))
        upsert_avatar_with_vrm(
            conn,
            avatar_id=f"{str(ng_row[0]).lower()}/shapey",
            collection_id="neonglitch86-collection-polygon-side",
            name="NG86SHAPE (shapey)",
            canon_url=canon,
            extracted_at=generated_at,
            vrm_spec=str(ng.get("vrmSpec") or "1.0"),
            thumbnail_url=ng_row[1],
            raw_meta=ng.get("rawMeta"),
            content_length=ng.get("totalLength"),
            content_sha256=ng.get("contentSha256"),
            json_chunk_sha256=ng.get("jsonChunkSha256"),
            observed_content_length=ng.get("observedLength"),
            transport_url=ng.get("transportUrl"),
        )
        summary["neonglitch86-collection-polygon-side"] = 1

    return summary


def sync_all(
    db_path: Path = DEFAULT_DB,
    inventory_path: Path = DEFAULT_INVENTORY,
    probe_path: Path = DEFAULT_PROBE,
    probed_new_path: Path = DEFAULT_PROBED_NEW,
) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        inv_counts = sync_inventory_probes(conn, inventory_path, probe_path)
        new_counts = sync_probed_new_sets(conn, probed_new_path)
        conn.commit()
    finally:
        conn.close()
    return {"inventorySynced": inv_counts, "probedSetsSynced": new_counts}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    ap.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    ap.add_argument("--probed-new", type=Path, default=DEFAULT_PROBED_NEW)
    args = ap.parse_args()
    print(json.dumps(sync_all(args.db, args.inventory, args.probe, args.probed_new), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
