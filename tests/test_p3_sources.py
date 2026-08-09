"""Tests for P3 source scanners (NFTScan + objkt).

These tests stay offline. The source scripts may call external APIs in normal
use, but their parsing, lead classification, validation gate, and import gate
are pure enough to lock locally.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sources import nftscan, objkt  # noqa: E402


def test_nftscan_items_accepts_nested_envelopes():
    assert nftscan._items({"data": {"content": [{"name": "A"}]}}) == [{"name": "A"}]
    assert nftscan._items({"data": {"list": [{"name": "B"}]}}) == [{"name": "B"}]
    assert nftscan._items({"collections": [{"name": "C"}]}) == [{"name": "C"}]


def test_nftscan_name_description_matches_are_leads_only():
    row = {
        "name": "Linea VRM Avatars",
        "description": "On-chain 3D avatar collection",
        "contract_address": "0x" + "1" * 40,
    }
    cand = nftscan._candidate_from_collection(row, "linea")
    assert cand["lead"] is True
    assert cand["validated"] is None
    assert cand["reason"] == "name/description match"


def test_nftscan_rewrites_ipfs_without_lowercasing_cid():
    assert nftscan.rewrite_storage_url("ipfs://BaSe58CID/Avatar.vrm") == \
        "https://ipfs.io/ipfs/BaSe58CID/Avatar.vrm"


def test_nftscan_validation_requires_binary_vrm_hit(monkeypatch):
    row = {"name": "VRM Lead", "contract_address": "0x" + "2" * 40}
    cand = nftscan._candidate_from_collection(row, "linea")

    monkeypatch.setattr(
        nftscan,
        "fetch_sample_assets",
        lambda contract, chain, limit: [{"metadata": {"vrm_url": "https://example.test/avatar.vrm"}}],
    )
    monkeypatch.setattr(
        nftscan,
        "validate_candidates",
        lambda candidates: [{**candidates[0], "valid": True, "vrm_spec": "1.0"}],
    )

    validated = nftscan.validate_candidate(cand)
    assert validated["validated"] is True
    assert validated["vrm_url"] == "https://example.test/avatar.vrm"
    assert validated["vrm_spec"] == "1.0"


def test_nftscan_import_gate_skips_unvalidated(tmp_path):
    db = tmp_path / "vrm.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE collections (id TEXT, name TEXT, tier TEXT, chain TEXT, contract TEXT, vrm_param TEXT, vrm_url_pattern TEXT, source TEXT, notes TEXT)")
    conn.execute("CREATE TABLE collection_identifiers (collection_id TEXT, namespace TEXT, value TEXT, chain TEXT, contract TEXT, verified_at TEXT, resolution_source TEXT, chain_namespace TEXT, chain_reference TEXT, asset_namespace TEXT)")
    conn.commit()
    conn.close()

    summary = nftscan.import_validated([
        {"name": "Lead", "contract": "0x" + "3" * 40, "chain": "linea", "validated": False}
    ], str(db), dry_run=False)

    assert summary == {"checked": 1, "imported": 0, "skipped": 1}
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0] == 0
    conn.close()


def test_objkt_tokens_accepts_graphql_envelope():
    assert objkt._tokens({"data": {"token": [{"name": "A"}]}}) == [{"name": "A"}]
    assert objkt._tokens({"token": [{"name": "B"}]}) == [{"name": "B"}]


def test_objkt_name_description_matches_are_leads_only():
    token = {
        "name": "Tezos VRM Avatar",
        "description": "A virtual avatar",
        "fa_contract": "KT1Example",
        "token_id": "7",
    }
    cand = objkt._candidate_from_token(token)
    assert cand["chain"] == "tezos"
    assert cand["lead"] is True
    assert cand["validated"] is None


def test_objkt_rewrites_ipfs_without_lowercasing_cid():
    assert objkt.rewrite_storage_url("ipfs://BaSe58CID/Avatar.vrm") == \
        "https://ipfs.io/ipfs/BaSe58CID/Avatar.vrm"


def test_objkt_validation_requires_binary_vrm_hit(monkeypatch):
    token = {
        "name": "VRM Token",
        "fa_contract": "KT1Example",
        "token_id": "7",
        "metadata": {"files": [{"uri": "https://example.test/model.vrm", "type": "model/vrm"}]},
    }
    cand = objkt._candidate_from_token(token)

    monkeypatch.setattr(
        objkt,
        "validate_candidates",
        lambda candidates: [{**candidates[0], "valid": True, "vrm_spec": "0.x"}],
    )

    validated = objkt.validate_candidate(cand)
    assert validated["validated"] is True
    assert validated["vrm_url"] == "https://example.test/model.vrm"
    assert validated["vrm_spec"] == "0.x"


def test_objkt_import_gate_skips_unvalidated(tmp_path):
    db = tmp_path / "vrm.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE collections (id TEXT, name TEXT, tier TEXT, chain TEXT, contract TEXT, vrm_param TEXT, vrm_url_pattern TEXT, source TEXT, notes TEXT, chain_namespace TEXT, chain_reference TEXT)")
    conn.execute("CREATE TABLE collection_identifiers (collection_id TEXT, namespace TEXT, value TEXT, chain TEXT, contract TEXT, token_id TEXT, verified_at TEXT, resolution_source TEXT, chain_namespace TEXT, chain_reference TEXT, asset_namespace TEXT)")
    conn.commit()
    conn.close()

    summary = objkt.import_validated([
        {"name": "Lead", "contract": "KT1Example", "token_id": "7", "validated": False}
    ], str(db), dry_run=False)

    assert summary == {"checked": 1, "imported": 0, "skipped": 1}
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0] == 0
    conn.close()
