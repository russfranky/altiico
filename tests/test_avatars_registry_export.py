"""Tests for scripts/export_avatars_registry.py.

The registry projection must obey the pre-alpha packages/avatars canonical
schema (schema/src/avatar.ts, SCHEMA_VERSION 1). The two locked design rules —
chain is a fixed enum (or null) and is orthogonal to storage — are asserted
here so a future edit cannot silently emit a chain the downstream enum cannot
represent, or fold a storage provider into the chain field.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_avatars_registry import (  # noqa: E402
    PREALPHA_CHAINS,
    STORAGE_PROVIDERS,
    _row_factory,
    build_entry,
    build_registry,
    load_collections,
)

DB_PATH = _REPO_ROOT / "data" / "vrm_index.db"


@pytest.fixture(scope="module")
def registry() -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = load_collections(conn, {"A", "B"})
    finally:
        conn.close()
    return build_registry(rows)


def test_db_present():
    assert DB_PATH.exists(), f"vrm_index.db missing at {DB_PATH}"


def test_top_level_shape(registry):
    assert registry["schema"] == "hubzz-avatars-registry-v1"
    assert registry["source"] == "vrm-catalog"
    assert isinstance(registry["collections"], list) and registry["collections"]
    assert isinstance(registry["unmapped"], list)


def test_chain_is_enum_or_null(registry):
    """Locked rule: chain is a fixed enum or null — never a coerced value."""
    for c in registry["collections"]:
        assert c["chain"] is None or c["chain"] in PREALPHA_CHAINS, (
            f"{c['slug']}: illegal chain {c['chain']!r}"
        )


def test_storage_provider_is_enum(registry):
    for c in registry["collections"]:
        assert c["storage_provider"] in STORAGE_PROVIDERS, (
            f"{c['slug']}: illegal storage_provider {c['storage_provider']!r}"
        )


def test_chain_and_storage_are_orthogonal(registry):
    """Storage-provider values (arweave/ipfs) must never leak into `chain`."""
    for c in registry["collections"]:
        assert c["chain"] not in {"arweave", "ipfs"}, (
            f"{c['slug']}: storage provider leaked into chain"
        )


def test_unmapped_chains_are_nulled_not_coerced(registry):
    """A chain outside the enum must be null AND recorded under unmapped."""
    unmapped_slugs = {u["slug"] for u in registry["unmapped"]}
    by_slug = {c["slug"]: c for c in registry["collections"]}
    for slug in unmapped_slugs:
        assert by_slug[slug]["chain"] is None, f"{slug}: unmapped chain not nulled"
    for u in registry["unmapped"]:
        assert u.get("original_chain"), f"{u['slug']}: unmapped note lacks original_chain"


def test_purchase_gated_is_bool(registry):
    for c in registry["collections"]:
        assert isinstance(c["purchase_gated"], bool)


def test_slugs_unique(registry):
    slugs = [c["slug"] for c in registry["collections"]]
    assert len(slugs) == len(set(slugs)), "duplicate slug in registry"


def test_required_fields_present(registry):
    required = {"slug", "name", "license", "chain", "storage_provider",
               "contract", "purchase_gated", "status"}
    for c in registry["collections"]:
        missing = required - set(c)
        assert not missing, f"{c['slug']}: missing {missing}"


def test_cc0_set_is_not_gated(registry):
    """A CC0 set is open by definition — it must not be purchase-gated."""
    for c in registry["collections"]:
        if c["license"] == "CC0":
            assert c["purchase_gated"] is False, f"{c['slug']}: CC0 but gated"


def test_no_secrets_in_registry(registry):
    """Guard against key/token leakage. Match real credential indicators, not
    the word "secret" (which appears legitimately in NFT descriptions)."""
    import json
    blob = json.dumps(registry).lower()
    for needle in ("api_key", "apikey", "opensea_api_key", "private_key",
                   "-----begin", "authorization:", "bearer "):
        assert needle not in blob, f"possible secret token {needle!r} in registry"


# ─── unit: mapping rules ───────────────────────────────────────────────────


def test_build_entry_splits_arweave_chain_to_storage():
    row = {"id": "x", "name": "X", "chain": "arweave", "vrm_url_pattern": "ar://abc/{id}.vrm",
           "vrm_license": "CC0", "tier": "A"}
    entry, note = build_entry(row)
    assert entry["chain"] is None          # arweave is not a chain
    assert entry["storage_provider"] == "arweave"
    assert note is None                    # null-because-CC0 is not an "unmapped" chain


def test_build_entry_flags_offenum_chain():
    row = {"id": "y", "name": "Y", "chain": "shape", "vrm_url_pattern": "https://h/{id}.vrm",
           "vrm_license": "CC0", "tier": "A"}
    entry, note = build_entry(row)
    assert entry["chain"] is None
    assert note is not None and note["original_chain"] == "shape"


def test_build_entry_ipfs_pattern_is_ipfs_storage():
    row = {"id": "z", "name": "Z", "chain": "ethereum",
           "vrm_url_pattern": "ipfs://bafy/{id}.vrm", "vrm_license": "CC-BY", "tier": "A"}
    entry, _ = build_entry(row)
    assert entry["chain"] == "ethereum"
    assert entry["storage_provider"] == "ipfs"


def test_redistribution_prohibited_is_gated_and_labeled():
    row = {"id": "r", "name": "R", "chain": "ethereum",
           "vrm_license": "Redistribution_Prohibited", "license_category": "red", "tier": "A"}
    entry, _ = build_entry(row)
    assert entry["license"] == "All Rights Reserved"
    assert entry["purchase_gated"] is True
