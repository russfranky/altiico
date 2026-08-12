import sqlite3

import pytest

from scripts.reconcile_moralis_validated_hits import (
    complete_proof,
    identity_matches,
    reconcile_hit,
)


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE collections (
          id TEXT PRIMARY KEY, name TEXT, chain TEXT, contract TEXT,
          vrm_url_https TEXT, vrm_reachable INTEGER, vrm_check_status TEXT,
          vrm_check_bytes INTEGER, vrm_check_url TEXT, vrm_checked_at TEXT
        );
        CREATE TABLE contracts (
          collection_id TEXT, address TEXT, chain TEXT, is_primary INTEGER DEFAULT 0,
          PRIMARY KEY(collection_id,address),
          FOREIGN KEY(collection_id) REFERENCES collections(id)
        );
        CREATE TABLE avatars (
          id TEXT PRIMARY KEY, collection_id TEXT, name TEXT, model_file_url TEXT,
          format TEXT, is_public INTEGER, metadata_json TEXT,
          reachable INTEGER, check_status TEXT, checked_at TEXT,
          FOREIGN KEY(collection_id) REFERENCES collections(id)
        );
        CREATE TABLE vrm_metadata (
          source_url TEXT PRIMARY KEY, extracted_at TEXT, extractor_version TEXT,
          vrm_spec TEXT, vrm_meta_json TEXT, parse_error TEXT, content_length INTEGER,
          content_sha256 TEXT, json_chunk_sha256 TEXT, observed_content_length INTEGER,
          transport_url TEXT
        );
        CREATE TABLE avatar_vrm (
          avatar_id TEXT PRIMARY KEY, vrm_source_url TEXT,
          FOREIGN KEY(avatar_id) REFERENCES avatars(id),
          FOREIGN KEY(vrm_source_url) REFERENCES vrm_metadata(source_url)
        );
        CREATE TABLE promotion_candidates (
          candidate_id TEXT PRIMARY KEY, collection_id TEXT, canonical_url TEXT,
          sha256 TEXT, promotion_state TEXT, reason TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO collections(id,name,chain,contract) VALUES (?,?,?,?)",
        ("dickbuttverse", "DickButtVerse", "ethereum", "0xd47d8672e45a7204057baaa3622a3fa276d651e3"),
    )
    return conn


def hit(**overrides):
    row = {
        "catalogId": "dickbuttverse",
        "collectionId": "dickbuttverse",
        "name": "DickButtVerse",
        "chain": "ethereum",
        "contract": "0xd47d8672e45a7204057baaa3622a3fa276d651e3",
        "tokenId": "1010",
        "tokenUri": "https://example.test/1010.json",
        "canonical_url": "https://example.test/1010.vrm",
        "transport_url": "https://example.test/1010.vrm",
        "status": "valid_vrm",
        "vrm_spec": "0.x",
        "sha256": "a" * 64,
        "json_chunk_sha256": "b" * 64,
        "byte_length": 672548,
        "observedAt": "2026-08-12T18:33:10+00:00",
        "sourcePath": "$.metadata",
    }
    row.update(overrides)
    return row


def test_complete_proof_is_strict():
    assert complete_proof(hit())
    assert not complete_proof(hit(status="valid_glb_not_vrm"))
    assert not complete_proof(hit(sha256=None))
    assert not complete_proof(hit(vrm_spec=None))


def test_identity_requires_existing_exact_chain_and_contract():
    conn = db()
    assert identity_matches(conn, hit()) == (True, "collection_primary_contract")
    assert identity_matches(conn, hit(chain="base")) == (False, "chain_mismatch")
    assert identity_matches(
        conn, hit(contract="0x1111111111111111111111111111111111111111")
    ) == (False, "contract_mismatch")


def test_secondary_contract_table_is_accepted():
    conn = db()
    secondary = "0x1111111111111111111111111111111111111111"
    conn.execute(
        "INSERT INTO contracts(collection_id,address,chain) VALUES (?,?,?)",
        ("dickbuttverse", secondary, "ethereum"),
    )
    assert identity_matches(conn, hit(contract=secondary)) == (
        True,
        "collection_contract_table",
    )


def test_reconcile_materializes_avatar_binary_proof_and_collection_sample():
    conn = db()
    conn.execute(
        "INSERT INTO promotion_candidates VALUES (?,?,?,?,?,?)",
        ("candidate", "dickbuttverse", hit()["canonical_url"], "a" * 64, "ready_for_reconciliation", "pending"),
    )

    result = reconcile_hit(conn, hit(), "2026-08-12T19:00:00Z")

    avatar = conn.execute("SELECT * FROM avatars").fetchone()
    assert avatar["id"] == "dickbuttverse:1010"
    assert avatar["collection_id"] == "dickbuttverse"
    assert avatar["check_status"] == "ok_vrm"
    assert avatar["reachable"] == 1

    proof = conn.execute("SELECT * FROM vrm_metadata").fetchone()
    assert proof["vrm_spec"] == "0.x"
    assert proof["content_sha256"] == "a" * 64
    assert proof["content_length"] == 672548

    link = conn.execute("SELECT * FROM avatar_vrm").fetchone()
    assert link["avatar_id"] == "dickbuttverse:1010"
    assert link["vrm_source_url"] == hit()["canonical_url"]

    collection = conn.execute("SELECT * FROM collections").fetchone()
    assert collection["vrm_check_status"] == "ok_vrm"
    assert collection["vrm_url_https"] == hit()["transport_url"]
    assert collection["vrm_check_bytes"] == 672548

    queued = conn.execute("SELECT promotion_state FROM promotion_candidates").fetchone()[0]
    assert queued == "reconciled"
    assert result["collectionUpdated"] is True


def test_existing_confirmed_collection_url_is_never_replaced():
    conn = db()
    conn.execute(
        "UPDATE collections SET vrm_check_status='ok_vrm', vrm_url_https='https://existing.test/sample.vrm' WHERE id='dickbuttverse'"
    )

    result = reconcile_hit(conn, hit(), "2026-08-12T19:00:00Z")

    collection = conn.execute("SELECT * FROM collections").fetchone()
    assert collection["vrm_url_https"] == "https://existing.test/sample.vrm"
    assert result["collectionUpdated"] is False
    assert conn.execute("SELECT COUNT(*) FROM avatar_vrm").fetchone()[0] == 1


def test_avatar_collision_is_rejected():
    conn = db()
    conn.execute(
        "INSERT INTO avatars(id,collection_id,model_file_url) VALUES (?,?,?)",
        ("dickbuttverse:1010", "dickbuttverse", "https://other.test/file.vrm"),
    )
    with pytest.raises(ValueError, match="different model URL"):
        reconcile_hit(conn, hit(), "2026-08-12T19:00:00Z")
