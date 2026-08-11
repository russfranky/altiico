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
    conn.close()


def test_reachable_avatar_inventory_becomes_bulk_ready(tmp_path):
    conn = make_db()
    row = insert_collection(conn, avatar_count=2, total_supply=2)
    conn.executemany(
        """
        INSERT INTO avatars
            (id, collection_id, name, model_file_url, reachable, check_status)
        VALUES (?, 'test-set', ?, ?, 1, 'ok_vrm')
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
            ("1", "One", "https://example.test/1.vrm", 1, "ok_vrm"),
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
    assert bundle["sets"][0]["set"]["slug"] == "ready"
    assert bundle["deferred"][0]["slug"] == "blocked"
    conn.close()
