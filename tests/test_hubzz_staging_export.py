"""Offline tests for the Hubzz pre-alpha staging bundle exporter."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_hubzz_staging import build_bundle, stage_record, validate_bundle  # noqa: E402


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE collections (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT,
            chain TEXT,
            contract TEXT,
            release_date TEXT,
            vrm_url_https TEXT,
            vrm_url_pattern TEXT,
            vrm_param TEXT,
            vrm_check_status TEXT,
            vrm_check_bytes INTEGER,
            vrm_checked_at TEXT,
            license_category TEXT,
            vrm_license TEXT,
            allowed_user TEXT,
            redistribution TEXT,
            source TEXT,
            creator TEXT,
            description TEXT,
            total_supply INTEGER,
            max_supply INTEGER,
            avatar_count INTEGER,
            image_url TEXT,
            banner_image_url TEXT,
            sample_nft_image TEXT,
            sample_nft_name TEXT,
            sample_metadata_url TEXT,
            owner_decision TEXT,
            is_nsfw INTEGER
        );
        CREATE TABLE contracts (
            collection_id TEXT,
            address TEXT,
            chain TEXT,
            token_standard TEXT,
            is_primary INTEGER
        );
        CREATE TABLE avatars (
            id TEXT PRIMARY KEY,
            collection_id TEXT,
            name TEXT,
            model_file_url TEXT,
            thumbnail_url TEXT,
            metadata_json TEXT,
            reachable INTEGER,
            check_status TEXT,
            checked_at TEXT,
            check_http INTEGER
        );
        CREATE TABLE vrm_metadata (
            source_url TEXT PRIMARY KEY,
            extracted_at TEXT,
            extractor_version TEXT,
            vrm_spec TEXT,
            vrm_meta_json TEXT,
            parse_error TEXT,
            content_length INTEGER
        );
        CREATE TABLE avatar_vrm (
            avatar_id TEXT PRIMARY KEY,
            vrm_source_url TEXT
        );
        """
    )
    return conn


def insert_collection(conn: sqlite3.Connection, **overrides) -> sqlite3.Row:
    values = {
        "id": "test-set",
        "name": "Test Set",
        "tier": "A",
        "chain": "ethereum",
        "contract": "0x" + "1" * 40,
        "vrm_url_https": "https://example.test/avatar.vrm",
        "vrm_check_status": "ok_vrm",
        "vrm_check_bytes": 1234,
        "vrm_checked_at": "2026-08-11T00:00:00Z",
        "license_category": "green",
        "vrm_license": "CC0",
        "allowed_user": "everyone",
        "redistribution": "allow",
        "source": "curated",
        "description": "A tested set",
        "total_supply": 1,
        "image_url": "https://example.test/pfp.png",
        "banner_image_url": "https://example.test/banner.png",
        "is_nsfw": 0,
    }
    values.update(overrides)
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO collections ({columns}) VALUES ({marks})", tuple(values.values()))
    conn.commit()
    return conn.execute("SELECT * FROM collections WHERE id=?", (values["id"],)).fetchone()


def test_validated_sample_becomes_unlisted_preview(tmp_path):
    conn = make_db()
    row = insert_collection(conn)
    entry, deferred = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is not None
    assert deferred["reasons"] == []
    assert entry["stageClass"] == "preview_ready"
    assert entry["set"]["status"] == "staged"
    assert entry["set"]["listed"] is False
    assert entry["set"]["purchaseGated"] is False
    assert entry["sourceAssets"]["count"] == 1
    assert entry["sourceAssets"]["binaryValidatedCount"] == 1
    conn.close()


def test_reachable_inventory_uses_collection_binary_proof(tmp_path):
    conn = make_db()
    row = insert_collection(conn, avatar_count=2, total_supply=2)
    conn.executemany(
        """
        INSERT INTO avatars
            (id, collection_id, name, model_file_url, reachable, check_status)
        VALUES (?, 'test-set', ?, ?, 1, 'ok_glb')
        """,
        [
            ("1", "One", "ipfs://bafy-one/1.vrm"),
            ("2", "Two", "ipfs://bafy-two/2.vrm"),
        ],
    )
    conn.commit()
    entry, _ = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is not None
    assert entry["stageClass"] == "bulk_ready"
    assert entry["set"]["avatarCount"] == 2
    assert entry["coverage"]["coverageRatio"] == 1.0
    assert entry["sourceAssets"]["binaryValidatedCount"] == 0
    assert entry["sourceAssets"]["validationScope"] == "collection_binary_plus_avatar_reachability"
    conn.close()


def test_partial_inventory_is_labeled_not_overstated(tmp_path):
    conn = make_db()
    row = insert_collection(conn, avatar_count=3, total_supply=3)
    conn.executemany(
        """
        INSERT INTO avatars
            (id, collection_id, name, model_file_url, reachable, check_status)
        VALUES (?, 'test-set', ?, ?, ?, ?)
        """,
        [
            ("1", "One", "https://example.test/1.vrm", 1, "ok_glb"),
            ("2", "Two", "https://example.test/2.vrm", 0, "http_404"),
            ("3", "Three", "https://example.test/3.vrm", 0, None),
        ],
    )
    conn.commit()
    entry, _ = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is not None
    assert entry["stageClass"] == "partial_ready"
    assert entry["set"]["avatarCount"] == 1
    assert "partial_avatar_inventory" in entry["warnings"]
    conn.close()


def test_reachable_glb_without_any_binary_vrm_proof_is_deferred(tmp_path):
    conn = make_db()
    row = insert_collection(
        conn,
        vrm_url_https=None,
        vrm_check_status=None,
        vrm_check_bytes=None,
        vrm_checked_at=None,
    )
    conn.execute(
        """
        INSERT INTO avatars
            (id, collection_id, name, model_file_url, reachable, check_status)
        VALUES ('1', 'test-set', 'One', 'https://example.test/1.vrm', 1, 'ok_glb')
        """
    )
    conn.commit()
    entry, deferred = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is None
    assert "no_binary_validated_vrm" in deferred["reasons"]
    conn.close()


def test_individually_validated_avatar_can_stage_without_collection_sample(tmp_path):
    conn = make_db()
    row = insert_collection(
        conn,
        vrm_url_https=None,
        vrm_check_status=None,
        vrm_check_bytes=None,
        vrm_checked_at=None,
    )
    conn.execute(
        """
        INSERT INTO avatars
            (id, collection_id, name, model_file_url, reachable, check_status)
        VALUES ('1', 'test-set', 'One', 'ipfs://bafy/1.vrm', 1, 'ok_glb')
        """
    )
    conn.execute(
        """
        INSERT INTO vrm_metadata
            (source_url, extracted_at, extractor_version, vrm_spec, parse_error, content_length)
        VALUES ('ipfs://bafy/1.vrm', '2026-08-11T00:00:00Z', 'test', '1.0', NULL, 900)
        """
    )
    conn.execute("INSERT INTO avatar_vrm VALUES ('1', 'ipfs://bafy/1.vrm')")
    conn.commit()
    entry, deferred = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is not None
    assert deferred["reasons"] == []
    assert entry["sourceAssets"]["binaryValidatedCount"] == 1
    assert entry["sourceAssets"]["validationScope"] == "per_avatar_binary"
    conn.close()


def test_evidence_contract_overrides_historical_primary(tmp_path):
    conn = make_db()
    old = "0x" + "1" * 40
    proven = "0x" + "2" * 40
    row = insert_collection(conn, contract=old)
    conn.executemany(
        "INSERT INTO contracts VALUES ('test-set', ?, 'ethereum', 'ERC-721', ?)",
        [(old, 1), (proven, 0)],
    )
    conn.commit()
    entry, _ = stage_record(
        conn,
        row,
        "2026-08-11T00:00:00Z",
        tmp_path,
        {"test-set": ("ethereum", proven)},
    )
    assert entry is not None
    assert entry["set"]["contract"] == proven
    assert entry["sampleEvidence"]["contract"] == proven
    conn.close()


def test_unsupported_ownership_chain_is_deferred(tmp_path):
    conn = make_db()
    row = insert_collection(conn, chain="shape")
    entry, deferred = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is None
    assert "unsupported_chain:shape" in deferred["reasons"]
    conn.close()


def test_storage_only_arweave_is_not_treated_as_ownership_chain(tmp_path):
    conn = make_db()
    row = insert_collection(
        conn,
        chain="arweave",
        contract=None,
        vrm_url_https="https://arweave.net/example",
    )
    entry, deferred = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is not None
    assert deferred["reasons"] == []
    assert entry["set"]["chain"] is None
    assert entry["set"]["storageProvider"] == "arweave"
    conn.close()


def test_unknown_license_stays_review_state(tmp_path):
    conn = make_db()
    row = insert_collection(
        conn,
        license_category="unknown",
        vrm_license=None,
        allowed_user="unknown",
        redistribution="unknown",
    )
    entry, _ = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is not None
    assert entry["set"]["purchaseGated"] is None
    assert "license_requires_review" in entry["warnings"]
    conn.close()


def test_positive_avatar_count_wins_over_zero_supply(tmp_path):
    conn = make_db()
    row = insert_collection(conn, total_supply=0, avatar_count=9)
    entry, _ = stage_record(conn, row, "2026-08-11T00:00:00Z", tmp_path)
    assert entry is not None
    assert entry["set"]["totalMints"] == 9
    conn.close()


def test_bundle_validation_and_summary(tmp_path):
    conn = make_db()
    insert_collection(conn, id="ready", name="Ready")
    insert_collection(
        conn,
        id="blocked",
        name="Blocked",
        vrm_url_https=None,
        vrm_check_status=None,
    )
    bundle = build_bundle(conn, tmp_path / "hubzz-prealpha-staging.json")
    assert validate_bundle(bundle) == []
    assert bundle["summary"]["stageableSets"] == 1
    assert bundle["summary"]["deferredSets"] == 1
    assert bundle["summary"]["binaryValidatedSourceAvatars"] == 1
    assert bundle["sets"][0]["set"]["slug"] == "ready"
    assert bundle["deferred"][0]["slug"] == "blocked"
    conn.close()
