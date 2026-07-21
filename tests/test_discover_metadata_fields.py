"""Tests for scripts/discover_metadata_fields.py — the VRM pointer scanner.

Pure logic tests (no network). The validation path (validate_candidates) hits
the network via extract_vrm_meta and is not exercised here; only the scanning
and classification logic is locked.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discover_metadata_fields import (  # noqa: E402
    scan_metadata,
    meets_tier_a,
    _is_vrm_url,
    _looks_like_url,
    VRM_FIELD_NAMES,
)


def test_finds_vrm_url_field():
    meta = {"vrm_url": "ipfs://QmFoo/bar.vrm"}
    cands = scan_metadata(meta)
    assert len(cands) == 1
    assert cands[0]["url"] == "ipfs://QmFoo/bar.vrm"
    assert cands[0]["reason"] == "field_name"


def test_finds_animation_url_ending_vrm():
    meta = {"animation_url": "https://x/y.vrm"}
    cands = scan_metadata(meta)
    assert len(cands) == 1
    assert cands[0]["reason"] == "animation_url"


def test_skips_non_vrm_animation_url():
    meta = {"animation_url": "https://x/y.mp4"}
    assert scan_metadata(meta) == []


def test_finds_files_uri_vrm():
    meta = {"files": [{"uri": "https://z/model.vrm"}, {"uri": "https://z/img.png"}]}
    cands = scan_metadata(meta)
    assert len(cands) == 1
    assert cands[0]["url"] == "https://z/model.vrm"
    assert cands[0]["reason"] == "vrm_extension"


def test_finds_nested_avatar_url():
    meta = {"properties": {"avatar_url": "https://deep/avatar.vrm"}}
    cands = scan_metadata(meta)
    assert len(cands) == 1
    assert cands[0]["path"] == "$.properties.avatar_url"


def test_case_insensitive_field_names():
    meta = {"VRM_URL": "https://x/y.vrm", "Avatar_Url": "https://x/a.vrm"}
    cands = scan_metadata(meta)
    urls = {c["url"] for c in cands}
    assert "https://x/y.vrm" in urls
    assert "https://x/a.vrm" in urls


def test_skips_description_with_vrm_url_text():
    """A .vrm string in a description/name field is not a pointer."""
    meta = {"description": "see https://x/y.vrm for details"}
    # description is excluded from the bare-string catch-all.
    cands = scan_metadata(meta)
    assert all(c["field"] != "description" for c in cands)


def test_vrm_extension_with_query_string():
    meta = {"image": "https://x/y.vrm?width=100"}
    cands = scan_metadata(meta)
    # 'image' is not in URL_LIKE_FIELDS, but the bare-string catch-all picks
    # up .vrm URLs in non-name/description fields.
    assert any(c["url"] == "https://x/y.vrm?width=100" for c in cands)


def test_is_vrm_url():
    assert _is_vrm_url("https://x/y.vrm")
    assert _is_vrm_url("https://x/y.vrm?token=1")
    assert _is_vrm_url("ipfs://QmFoo/bar.vrm")
    assert not _is_vrm_url("https://x/y.png")
    assert not _is_vrm_url("")
    assert not _is_vrm_url(None)


def test_looks_like_url():
    assert _looks_like_url("https://x")
    assert _looks_like_url("ipfs://x")
    assert _looks_like_url("ar://x")
    assert not _looks_like_url("not a url")
    assert not _looks_like_url(None)


def test_meets_tier_a_requires_validated():
    assert not meets_tier_a([])
    assert not meets_tier_a([{"valid": False}])
    assert meets_tier_a([{"valid": False}, {"valid": True}])


def test_multiple_candidates_in_complex_metadata():
    meta = {
        "name": "Test Collection",
        "vrm_url": "ipfs://a.vrm",
        "animation_url": "https://b.vrm",
        "files": [{"uri": "https://c.vrm"}, {"uri": "https://d.png"}],
        "attributes": [{"trait_type": "model", "value": "https://e.vrm"}],
    }
    cands = scan_metadata(meta)
    urls = {c["url"] for c in cands}
    assert "ipfs://a.vrm" in urls
    assert "https://b.vrm" in urls
    assert "https://c.vrm" in urls
    assert "https://d.png" not in urls
    # The trait value is a bare .vrm string in a non-excluded field.
    assert "https://e.vrm" in urls
