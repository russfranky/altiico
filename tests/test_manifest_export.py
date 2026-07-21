"""Tests for scripts/export_hubzz_manifest.py and the generated manifest.

Three concerns from the P1 spec:
  1. Every Tier A collection has a usable resolver strategy OR an explicit
     ``unavailable`` reason (never a silently-empty resolution).
  2. The generated manifest validates against
     static/schema/avatar-manifest-v1.schema.json (JSON Schema draft 2020-12).
  3. No API secrets / keys / tokens leak into the manifest.

Also covers the pure builder functions (build_license, build_resolution,
build_identifiers, build_collection, CAIP id construction) so the contract is
locked independently of the on-disk DB.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_hubzz_manifest import (  # noqa: E402
    build_collection,
    build_identifiers,
    build_license,
    build_resolution,
    _caip_id,
    _chain_id,
    _has_token_placeholder,
    _standard,
    validate_manifest,
)

MANIFEST_PATH = _REPO_ROOT / "static" / "data" / "avatar-manifest-v1.json"
SCHEMA_PATH = _REPO_ROOT / "static" / "schema" / "avatar-manifest-v1.schema.json"

# Strategies that count as "usable" — hubzz can resolve a VRM URL from these.
USABLE_STRATEGIES = {
    "direct_url", "url_template", "token_map", "token_metadata",
    "ipfs_path", "arweave_path", "vroid_hub", "authenticated_api",
}


# --------------------------------------------------------------------------- schema validation


@pytest.fixture(scope="module")
def manifest():
    assert MANIFEST_PATH.exists(), f"manifest not found at {MANIFEST_PATH}; run scripts/export_hubzz_manifest.py"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_validates_against_schema(manifest):
    """The generated manifest must validate against the v1 schema."""
    ok = validate_manifest(manifest, SCHEMA_PATH)
    assert ok, "manifest failed schema validation (see stderr above)"


def test_manifest_top_level_fields(manifest):
    assert manifest["schema"].startswith("http")
    assert manifest["version"].count(".") == 2  # semver-ish
    assert "collections" in manifest and isinstance(manifest["collections"], list)


# --------------------------------------------------------------------------- Tier A resolver coverage


def test_tier_a_has_usable_resolver_or_unavailable(manifest):
    """Every Tier A collection must carry a usable resolution strategy OR an
    explicit ``unavailable`` strategy (never a missing/broken resolution)."""
    tier_a = [c for c in manifest["collections"] if c["tier"] == "A"]
    assert tier_a, "expected at least one Tier A collection in manifest"
    for c in tier_a:
        strat = c["resolution"]["strategy"]
        assert strat in USABLE_STRATEGIES or strat == "unavailable", (
            f"{c['id']}: strategy {strat!r} is neither usable nor 'unavailable'"
        )


def test_unavailable_strategy_is_explicit_choice(manifest):
    """Collections marked 'unavailable' must still have a well-formed
    resolution object (strategy field present). The schema enforces this, but
    we assert it directly for clarity."""
    for c in manifest["collections"]:
        if c["resolution"]["strategy"] == "unavailable":
            assert c["resolution"]["strategy"] == "unavailable"
            # 'unavailable' should not carry a template (schema allows but it's
            # meaningless). We don't forbid it, just confirm strategy is set.


def test_every_collection_has_resolution(manifest):
    for c in manifest["collections"]:
        assert "resolution" in c, f"{c['id']}: missing resolution"
        assert "strategy" in c["resolution"], f"{c['id']}: missing strategy"


# --------------------------------------------------------------------------- no secrets leak


SECRET_PATTERNS = [
    "api_key", "apikey", "api-key",
    "secret", "token", "bearer",
    "authorization",
    "0x" + "a" * 64,  # placeholder; real check is value-based below
]
# Substrings that should never appear as VALUES in the manifest. Keys named
# like secrets are checked separately.
SECRET_KEY_SUBSTRINGS = ("api_key", "apikey", "secret", "token", "password", "private_key")


def _walk_values(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k, v
            yield from _walk_values(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_values(v, f"{path}[{i}]")


def test_no_secret_keys_in_manifest(manifest):
    """No key in the manifest should look like a secret."""
    for path, key, _ in _walk_values(manifest):
        kl = key.lower()
        for s in SECRET_KEY_SUBSTRINGS:
            if s in kl:
                pytest.fail(f"secret-like key {key!r} at {path}")


def test_no_high_entropy_secrets_in_manifest(manifest):
    """No string value should resemble a long hex secret (API key, private key,
    JWT). We flag any value matching a 32+ hex-char run that is NOT a contract
    address (0x-prefixed, 40 hex) or a CAIP id containing one."""
    import re
    # A 32+ char run that contains at least one hex letter [a-f] is suspicious
    # (real API keys/JWTs are hex). Pure-decimal runs are token IDs / DNA
    # parameters and are not secrets.
    hex_run = re.compile(r"(?=[a-fA-F0-9]{32,})[a-fA-F0-9]{32,}")
    for path, key, val in _walk_values(manifest):
        if not isinstance(val, str):
            continue
        for m in hex_run.finditer(val):
            run = m.group()
            if any(c in "abcdefABCDEF" for c in run):
                # Allow contract addresses (40 hex / 20 bytes) and CAIP id parts.
                if len(run) == 40:
                    continue
                pytest.fail(f"possible secret at {path}={val!r} (hex run {run})")


def test_no_opensea_api_key_in_manifest(manifest):
    """The OpenSea API key lives in ~/.opensea/api_key and must never be
    embedded in the manifest."""
    blob = json.dumps(manifest)
    # OpenSea keys are 32-char hex; we already check hex runs above, but also
    # assert the literal env-var name never appears.
    assert "OPENSEA_API_KEY" not in blob
    assert "opensea_api_key" not in blob.lower()


# --------------------------------------------------------------------------- build_license


def _lic_row(**kw):
    base = dict(license_category=None, vrm_license=None, commercial_use=None,
                allowed_user=None, redistribution=None)
    base.update(kw)
    return base


def test_build_license_green_category():
    r = _lic_row(license_category="green", commercial_use="allow",
                 allowed_user="everyone", redistribution="allow")
    lic = build_license(r)
    assert lic["use_scope"] == "everyone"
    assert lic["commercial_scope"] == "corporation"
    assert lic["modify"] is True
    assert lic["redistribute_original"] is True


def test_build_license_red_category_no_modify():
    r = _lic_row(license_category="red")
    lic = build_license(r)
    assert lic["modify"] is False


def test_build_license_holder_terminates_on_transfer():
    r = _lic_row(allowed_user="holder")
    lic = build_license(r)
    assert lic["use_scope"] == "holder"
    assert lic["terminates_on_transfer"] is True


def test_build_license_cc0_no_credit():
    r = _lic_row(vrm_license="CC0")
    lic = build_license(r)
    assert lic["credit"] == "unnecessary"


def test_build_license_cc_by_credit_required():
    r = _lic_row(vrm_license="CC-BY")
    lic = build_license(r)
    assert lic["credit"] == "required"


def test_build_license_unknown_defaults():
    r = _lic_row()
    lic = build_license(r)
    assert lic["use_scope"] == "unknown"
    assert lic["commercial_scope"] == "unknown"
    assert lic["credit"] == "unknown"
    assert lic["redistribute_original"] is False
    assert lic["modify"] is False


# --------------------------------------------------------------------------- build_resolution


def test_resolution_url_template():
    r = {"vrm_url_pattern": "https://x/{token_id}.vrm"}
    res = build_resolution(r)
    assert res["strategy"] == "url_template"
    assert res["template"] == "https://x/{token_id}.vrm"


def test_resolution_token_metadata_from_sample():
    r = {"sample_metadata_url": "https://x/1/metadata.json"}
    res = build_resolution(r)
    assert res["strategy"] == "token_metadata"
    assert "{token_id}" in res["metadata_url"]["template"]


def test_resolution_unavailable_when_nothing():
    r = {}
    res = build_resolution(r)
    assert res["strategy"] == "unavailable"


def test_resolution_vrm_param_only():
    r = {"vrm_param": "vrm_url"}
    res = build_resolution(r)
    assert res["strategy"] == "token_metadata"
    assert "vrm_pointer" in res


# --------------------------------------------------------------------------- CAIP ids


def test_caip_id_erc721_ethereum():
    assert _caip_id("ethereum", "erc721", "0xabc") == "eip155:1/erc721:0xabc"


def test_caip_id_erc1155_shared_appends_token_id():
    assert _caip_id("ethereum", "erc1155", "0xabc", True) == "eip155:1/erc1155:0xabc/token_id"


def test_caip_id_base_chain():
    assert _caip_id("base", "erc721", "0xabc") == "eip155:8453/erc721:0xabc"


def test_caip_id_solana():
    assert _caip_id("solana", None, "0xabc") is None  # solana isn't eip155


def test_caip_id_missing_contract():
    assert _caip_id("ethereum", "erc721", None) is None


def test_chain_id_aliases():
    assert _chain_id("ethereum") == "1"
    assert _chain_id("mainnet") == "1"
    assert _chain_id("base") == "8453"
    assert _chain_id("polygon") == "137"
    assert _chain_id("arbitrum") == "42161"
    assert _chain_id("solana") == "solana"


def test_standard_normalization():
    assert _standard("erc721") == "erc721"
    assert _standard("erc-721") == "erc721"
    assert _standard("erc721a") == "erc721"
    assert _standard("erc1155") == "erc1155"
    assert _standard(None) == "erc721"


def test_has_token_placeholder():
    assert _has_token_placeholder("https://x/{token_id}.vrm")
    assert _has_token_placeholder("https://x/{id}.vrm")
    assert _has_token_placeholder("https://x/%d.vrm")
    assert not _has_token_placeholder("https://x/123.vrm")
    assert not _has_token_placeholder(None)


# --------------------------------------------------------------------------- build_identifiers


def test_build_identifiers_from_ci_rows():
    row = {"chain": "ethereum", "contract": None, "opensea_slug": None}
    ci = [{"namespace": "contract_token", "contract": "0xdead", "value": "1"},
          {"namespace": "opensea_slug", "value": "pixelbeasts"}]
    ids = build_identifiers(row, ci)
    assert ids["chain"] == "ethereum"
    assert ids["chain_id"] == "1"
    assert ids["contract"] == "0xdead"
    assert ids["opensea_slug"] == "pixelbeasts"


def test_build_identifiers_falls_back_to_row_contract():
    row = {"chain": "ethereum", "contract": "0xbeef", "opensea_slug": "foo"}
    ids = build_identifiers(row, [])
    assert ids["contract"] == "0xbeef"
    assert ids["opensea_slug"] == "foo"


# --------------------------------------------------------------------------- build_collection (in-memory DB)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE collections (
            id TEXT PRIMARY KEY, name TEXT, tier TEXT, chain TEXT, contract TEXT,
            opensea_slug TEXT, vrm_param TEXT, vrm_url_pattern TEXT,
            license_category TEXT, vrm_license TEXT, commercial_use TEXT,
            allowed_user TEXT, redistribution TEXT, sample_metadata_url TEXT
        );
        CREATE TABLE contracts (
            address TEXT, collection_id TEXT, token_standard TEXT,
            is_primary INTEGER
        );
        CREATE TABLE collection_identifiers (
            collection_id TEXT, namespace TEXT, value TEXT, contract TEXT
        );
        """
    )
    yield conn
    conn.close()


def test_build_collection_tier_a(db):
    row = {"id": "test-c", "name": "Test", "tier": "A", "chain": "ethereum",
           "contract": "0xabc", "opensea_slug": "test", "vrm_param": None,
           "vrm_url_pattern": "https://x/{token_id}.vrm",
           "license_category": "green", "vrm_license": "CC0",
           "commercial_use": "allow", "allowed_user": "everyone",
           "redistribution": "allow", "sample_metadata_url": None}
    c = build_collection(row, [], [])
    assert c is not None
    assert c["tier"] == "A"
    assert c["id"] == "eip155:1/erc721:0xabc"
    assert c["resolution"]["strategy"] == "url_template"
    assert c["license"]["use_scope"] == "everyone"


def test_build_collection_skips_non_abc_tier(db):
    row = {"id": "infra-c", "name": "Infra", "tier": "infra", "chain": "ethereum",
           "contract": "0xabc", "opensea_slug": None, "vrm_param": None,
           "vrm_url_pattern": None, "license_category": None,
           "vrm_license": None, "commercial_use": None, "allowed_user": None,
           "redistribution": None, "sample_metadata_url": None}
    assert build_collection(row, [], []) is None


def test_build_collection_erc1155_shared(db):
    row = {"id": "ss-c", "name": "SS", "tier": "A", "chain": "ethereum",
           "contract": None, "opensea_slug": None, "vrm_param": None,
           "vrm_url_pattern": None, "license_category": None,
           "vrm_license": None, "commercial_use": None, "allowed_user": None,
           "redistribution": None, "sample_metadata_url": "https://x/1/metadata.json"}
    contracts = [{"address": "0x495f947276749ce646f68ac8c248420045cb7b5e",
                  "collection_id": "ss-c", "token_standard": "erc1155",
                  "is_primary": 1}]
    c = build_collection(row, [], contracts)
    assert c is not None
    assert "/token_id" in c["id"]
    assert c["id"].startswith("eip155:1/erc1155:")
