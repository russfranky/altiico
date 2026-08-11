from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.catalog_snapshot import compute_snapshot_id, record_snapshot
from scripts.verify_catalog_consistency import _canonical_contracts, verify


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT, contract TEXT, opensea_slug TEXT);
        CREATE TABLE source_cache (key TEXT PRIMARY KEY, response_json TEXT);
        INSERT INTO collections VALUES ('one', 'One', '0x1111111111111111111111111111111111111111', 'one');
        """
    )
    return conn


def test_snapshot_is_stable_and_ignores_transient_cache():
    conn = make_conn()
    first = compute_snapshot_id(conn)
    conn.execute("INSERT INTO source_cache VALUES ('x', '{}')")
    conn.commit()
    assert compute_snapshot_id(conn) == first
    assert record_snapshot(conn) == first
    assert compute_snapshot_id(conn) == first
    conn.close()


def test_snapshot_changes_when_canonical_data_changes():
    conn = make_conn()
    first = compute_snapshot_id(conn)
    conn.execute("UPDATE collections SET name='One updated' WHERE id='one'")
    conn.commit()
    assert compute_snapshot_id(conn) != first
    conn.close()


def test_primary_contract_row_overrides_stale_collection_mirror():
    conn = make_conn()
    conn.executescript(
        """
        CREATE TABLE contracts (
            collection_id TEXT,
            address TEXT,
            is_primary INTEGER
        );
        INSERT INTO contracts VALUES (
            'one',
            '0x2222222222222222222222222222222222222222',
            1
        );
        """
    )
    canonical, slug_to_id = _canonical_contracts(conn)
    assert canonical["one"] == "0x2222222222222222222222222222222222222222"
    assert slug_to_id["one"] == "one"
    conn.close()


def test_committed_artifacts_share_one_snapshot():
    root = Path(__file__).resolve().parent.parent
    errors = verify(
        root / "data" / "vrm_index.db",
        root / "static" / "data",
        root / "static",
    )
    assert errors == []
