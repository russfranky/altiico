"""Tests for scripts/normalize_licenses.py.

Covers every license family in config/license-mapping.yaml:
  - Creative Commons (CC0, CC-BY, CC-BY-NC, CC-BY-SA, CC-BY-ND, CC-BY-NC-SA,
    CC-BY-NC-ND)
  - VRM 0.x embedded meta (licenseName / allowedUserName / commercialUssageName,
    including the Redistribution_Prohibited special case and the intentional
    field-name misspellings)
  - VRM 1.0 embedded meta (restrictive defaults for omitted fields, plus the
    everyone + allowRedistribution=true case)
  - a16z "Can't Be Evil" — all 6 variants
  - External license URL recognition (creativecommons.org, a16z.com)
  - Legacy collection-level terms (vrm_license / commercial_use / allowed_user /
    redistribution)
  - Precedence + conflict detection across layers
  - Color derivation: unknown never promotes to green

No live API calls. The mapping YAML is loaded from config/license-mapping.yaml
(the single source of truth — testing against it is the point). The full
assess_collection() flow is exercised against an in-memory SQLite DB built from
the real migration schemas, so no on-disk database is touched.
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

from scripts.normalize_licenses import (  # noqa: E402
    assess_collection,
    evaluate_color,
    load_mapping,
    map_collection_terms,
    map_embedded_vrm_meta,
    resolve_url,
    _merge_layer,
    _empty_dimensions,
)

MAPPING = load_mapping()
COLOR_RULES = MAPPING["color_rules"]


# --------------------------------------------------------------------------- fixtures


def _dims_without_reasons(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "__reason_codes__"}


def _reasons(d: dict) -> list:
    return list(d.get("__reason_codes__", []))


@pytest.fixture
def db():
    """In-memory SQLite with the minimal schema assess_collection() touches."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE collections (
            id TEXT PRIMARY KEY, name TEXT, tier TEXT, chain TEXT, contract TEXT,
            opensea_slug TEXT, vrm_param TEXT, vrm_url_pattern TEXT,
            license_category TEXT, vrm_license TEXT, commercial_use TEXT,
            allowed_user TEXT, redistribution TEXT, description TEXT, notes TEXT,
            sample_metadata_url TEXT, project_url TEXT
        );
        CREATE TABLE avatars (
            id TEXT PRIMARY KEY, collection_id TEXT, name TEXT, description TEXT,
            model_file_url TEXT, format TEXT, thumbnail_url TEXT, is_public INTEGER,
            metadata_json TEXT
        );
        CREATE TABLE vrm_metadata (
            source_url TEXT PRIMARY KEY, source_etag TEXT, source_last_modified TEXT,
            extracted_at TEXT NOT NULL, extractor_version TEXT NOT NULL,
            vrm_spec TEXT, vrm_meta_json TEXT, parse_error TEXT,
            content_length INTEGER, content_range TEXT
        );
        CREATE TABLE avatar_vrm (
            avatar_id TEXT PRIMARY KEY, vrm_source_url TEXT
        );
        CREATE TABLE license_dimensions (
            collection_id TEXT PRIMARY KEY, raw_collection_terms TEXT,
            raw_embedded_vrm_meta_json TEXT, raw_external_urls TEXT,
            use_scope TEXT, commercial_scope TEXT, credit TEXT,
            redistribute_original INTEGER, modify INTEGER,
            redistribute_modified INTEGER, corporate_use INTEGER,
            terminates_on_transfer INTEGER, hate_speech_termination INTEGER,
            color TEXT, reason_codes TEXT, confidence TEXT,
            conflict_flag INTEGER DEFAULT 0, assessed_at TEXT
        );
        """
    )
    yield conn
    conn.close()


def _insert_collection(
    conn, cid="c1", *, vrm_license=None, commercial_use=None,
    allowed_user=None, redistribution=None, license_category=None,
    description=None, notes=None,
):
    conn.execute(
        """INSERT INTO collections
           (id, name, vrm_license, commercial_use, allowed_user, redistribution,
            license_category, description, notes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (cid, cid, vrm_license, commercial_use, allowed_user, redistribution,
         license_category, description, notes),
    )


def _insert_embedded(conn, cid, vrm_spec, meta, url="ipfs://vrm1"):
    conn.execute(
        "INSERT INTO avatars (id, collection_id) VALUES (?,?)",
        (f"{cid}-av1", cid),
    )
    conn.execute(
        """INSERT INTO vrm_metadata
           (source_url, extracted_at, extractor_version, vrm_spec, vrm_meta_json)
           VALUES (?,?,?,?,?)""",
        (url, "2026-01-01T00:00:00Z", "1.0.0", vrm_spec, json.dumps(meta)),
    )
    conn.execute(
        "INSERT INTO avatar_vrm (avatar_id, vrm_source_url) VALUES (?,?)",
        (f"{cid}-av1", url),
    )


# --------------------------------------------------------------------------- CC family


@pytest.mark.parametrize(
    "code,expected",
    [
        ("CC0", dict(use_scope="everyone", commercial_scope="personal_profit",
                     credit="unnecessary", redistribute_original=1, modify=1,
                     redistribute_modified=1)),
        ("CC-BY", dict(use_scope="everyone", commercial_scope="personal_profit",
                       credit="required", redistribute_original=1, modify=1,
                       redistribute_modified=1)),
        ("CC-BY-NC", dict(use_scope="everyone", commercial_scope="personal_non_profit",
                          credit="required", redistribute_original=1, modify=1,
                          redistribute_modified=1)),
        ("CC-BY-SA", dict(use_scope="everyone", commercial_scope="personal_profit",
                          credit="required", redistribute_original=1, modify=1,
                          redistribute_modified=1)),
        ("CC-BY-ND", dict(use_scope="everyone", commercial_scope="personal_profit",
                          credit="required", redistribute_original=1, modify=0,
                          redistribute_modified=0)),
        ("CC-BY-NC-SA", dict(use_scope="everyone", commercial_scope="personal_non_profit",
                             credit="required", redistribute_original=1, modify=1,
                             redistribute_modified=1)),
        ("CC-BY-NC-ND", dict(use_scope="everyone", commercial_scope="personal_non_profit",
                             credit="required", redistribute_original=1, modify=0,
                             redistribute_modified=0)),
    ],
)
def test_creative_commons_via_collection_terms(code, expected):
    """Each CC code maps to its canonical dimension set via collection terms."""
    dims = map_collection_terms({"vrm_license": code}, MAPPING)
    got = _dims_without_reasons(dims)
    for k, v in expected.items():
        assert got[k] == v, f"{code}: {k} expected {v!r} got {got[k]!r}"


def test_cc_by_nc_sets_non_commercial_reason():
    dims = map_collection_terms({"vrm_license": "CC-BY-NC"}, MAPPING)
    assert "NON_COMMERCIAL" in _reasons(dims)


def test_cc_by_nd_sets_no_derivatives_reason():
    dims = map_collection_terms({"vrm_license": "CC-BY-ND"}, MAPPING)
    assert "NO_DERIVATIVES" in _reasons(dims)


def test_cc_by_nc_nd_has_both_reasons():
    dims = map_collection_terms({"vrm_license": "CC-BY-NC-ND"}, MAPPING)
    r = _reasons(dims)
    assert "NON_COMMERCIAL" in r and "NO_DERIVATIVES" in r


def test_cc0_is_green():
    dims = map_collection_terms({"vrm_license": "CC0"}, MAPPING)
    assert evaluate_color(_dims_without_reasons(dims), COLOR_RULES) == "green"


def test_cc_by_nc_is_yellow():
    dims = map_collection_terms({"vrm_license": "CC-BY-NC"}, MAPPING)
    assert evaluate_color(_dims_without_reasons(dims), COLOR_RULES) == "yellow"


# --------------------------------------------------------------------------- VRM 0.x


def test_vrm_0x_field_misspellings_preserved():
    """VRM 0.x uses commercialUssageName (double-s) — read exactly as written."""
    meta = {
        "allowedUserName": "Everyone",
        "commercialUssageName": "Allow",
        "licenseName": "CC0",
    }
    dims = map_embedded_vrm_meta("0.x", meta, MAPPING)
    g = _dims_without_reasons(dims)
    assert g["use_scope"] == "everyone"
    assert g["commercial_scope"] == "personal_profit"
    assert g["credit"] == "unnecessary"
    assert g["redistribute_original"] == 1


def test_vrm_0x_redistribution_prohibited():
    meta = {"licenseName": "Redistribution_Prohibited"}
    dims = map_embedded_vrm_meta("0.x", meta, MAPPING)
    g = _dims_without_reasons(dims)
    assert g["redistribute_original"] == 0
    assert g["modify"] == 1
    assert g["redistribute_modified"] == 0
    assert "REDISTRIBUTION_PROHIBITED" in _reasons(dims)


def test_vrm_0x_only_author():
    meta = {"allowedUserName": "OnlyAuthor"}
    dims = map_embedded_vrm_meta("0.x", meta, MAPPING)
    assert _dims_without_reasons(dims)["use_scope"] == "author"
    assert "AUTHOR_ONLY" in _reasons(dims)


def test_vrm_0x_commercial_disallow():
    meta = {"commercialUssageName": "Disallow"}
    dims = map_embedded_vrm_meta("0.x", meta, MAPPING)
    assert _dims_without_reasons(dims)["commercial_scope"] == "none"
    assert "NO_COMMERCIAL" in _reasons(dims)


# --------------------------------------------------------------------------- VRM 1.0


def test_vrm_1_0_omitted_fields_are_restrictive():
    """VRM 1.0 defaults: onlyAuthor / personalNonProfit / required credit /
    no redistribution / prohibited modification. Color must NOT be green."""
    dims = map_embedded_vrm_meta("1.0", {}, MAPPING)
    g = _dims_without_reasons(dims)
    assert g["use_scope"] == "author"
    assert g["commercial_scope"] == "personal_non_profit"
    assert g["credit"] == "required"
    assert g["redistribute_original"] == 0
    assert g["modify"] == 0
    assert g["redistribute_modified"] == 0
    # Author-only + no redistribution → yellow (holder scope), not green.
    assert evaluate_color(g, COLOR_RULES) == "yellow"


def test_vrm_1_0_everyone_allow_redistribution_is_green():
    meta = {
        "avatarPermission": "everyone",
        "commercialUsage": "personalProfit",
        "creditNotation": "required",
        "allowRedistribution": "true",
        "modification": "allowModificationRedistribution",
    }
    dims = map_embedded_vrm_meta("1.0", meta, MAPPING)
    g = _dims_without_reasons(dims)
    assert g["use_scope"] == "everyone"
    assert g["commercial_scope"] == "personal_profit"
    assert g["redistribute_original"] == 1
    assert g["modify"] == 1
    assert g["redistribute_modified"] == 1
    assert evaluate_color(g, COLOR_RULES) == "green"


def test_vrm_1_0_corporation_sets_corporate_use():
    meta = {"commercialUsage": "corporation"}
    dims = map_embedded_vrm_meta("1.0", meta, MAPPING)
    g = _dims_without_reasons(dims)
    assert g["commercial_scope"] == "corporation"
    assert g["corporate_use"] == 1


def test_vrm_1_0_spec_dispatch():
    """Spec starting with '1' → 1.0 mapper; anything else → 0.x mapper."""
    assert map_embedded_vrm_meta("1.0", {"avatarPermission": "everyone"}, MAPPING)["use_scope"] == "everyone"
    assert map_embedded_vrm_meta("0.x", {"allowedUserName": "Everyone"}, MAPPING)["use_scope"] == "everyone"
    assert map_embedded_vrm_meta(None, {"allowedUserName": "Everyone"}, MAPPING)["use_scope"] == "everyone"


# --------------------------------------------------------------------------- a16z CBE (all 6)


A16Z_VARIANTS = ["PUBLIC", "EXCLUSIVE", "COMMERCIAL", "COMMERCIAL-NO-HATE",
                 "PERSONAL", "PERSONAL-NO-HATE"]


@pytest.mark.parametrize("variant", A16Z_VARIANTS)
def test_a16z_cbe_all_variants_resolve(variant):
    """Every a16z CBE variant resolves to a non-empty dimension set."""
    entry = MAPPING["a16z_cbe"][variant]
    from scripts.normalize_licenses import _entry_dimensions
    dims = _entry_dimensions(entry)
    assert dims.get("use_scope") is not None, f"{variant}: use_scope missing"
    # All a16z variants are holder-scoped except PUBLIC.
    if variant == "PUBLIC":
        assert dims["use_scope"] == "everyone"
        assert dims["corporate_use"] == 1
    else:
        assert dims["use_scope"] == "holder"
        assert dims["redistribute_original"] == 0


def test_a16z_exclusive_terminates_on_transfer():
    entry = MAPPING["a16z_cbe"]["EXCLUSIVE"]
    from scripts.normalize_licenses import _entry_dimensions
    dims = _entry_dimensions(entry)
    assert dims["terminates_on_transfer"] == 1
    assert "HOLDER_ONLY" in (entry.get("reason_codes") or [])


def test_a16z_commercial_no_hate_sets_hate_speech_termination():
    entry = MAPPING["a16z_cbe"]["COMMERCIAL-NO-HATE"]
    from scripts.normalize_licenses import _entry_dimensions
    dims = _entry_dimensions(entry)
    assert dims["hate_speech_termination"] == 1


def test_a16z_personal_is_not_green():
    """PERSONAL: holder + commercial_scope=none + no redistribution. Yellow
    matches first (redistribute_original=0 is a yellow condition_any), so it
    is never green. The key invariant: holder-gated → not green."""
    entry = MAPPING["a16z_cbe"]["PERSONAL"]
    from scripts.normalize_licenses import _entry_dimensions
    dims = _entry_dimensions(entry)
    assert dims["commercial_scope"] == "none"
    assert dims["use_scope"] == "holder"
    assert evaluate_color(dims, COLOR_RULES) != "green"


def test_a16z_public_is_green():
    entry = MAPPING["a16z_cbe"]["PUBLIC"]
    from scripts.normalize_licenses import _entry_dimensions
    dims = _entry_dimensions(entry)
    assert evaluate_color(dims, COLOR_RULES) == "green"


# --------------------------------------------------------------------------- URL recognition


def test_resolve_url_creative_commons_cc0():
    dims = resolve_url("https://creativecommons.org/publicdomain/zero/1.0/", MAPPING)
    assert dims is not None
    assert dims["credit"] == "unnecessary"
    assert dims["redistribute_original"] == 1


def test_resolve_url_creative_commons_by_nc():
    dims = resolve_url("https://creativecommons.org/licenses/by-nc/4.0/", MAPPING)
    assert dims is not None
    assert dims["commercial_scope"] == "personal_non_profit"


def test_resolve_url_a16z_exclusive():
    dims = resolve_url("https://a16z.com/cant-be-evil/exclusive", MAPPING)
    assert dims is not None
    assert dims["use_scope"] == "holder"
    assert dims["terminates_on_transfer"] == 1


def test_resolve_url_a16z_commercial_no_hate():
    dims = resolve_url("https://a16z.com/cant-be-evil/commercial-no-hate", MAPPING)
    assert dims is not None
    assert dims["hate_speech_termination"] == 1


def test_resolve_url_unknown_returns_none():
    assert resolve_url("https://example.com/some-license", MAPPING) is None


def test_resolve_url_empty_returns_none():
    assert resolve_url("", MAPPING) is None


# --------------------------------------------------------------------------- legacy collection terms


def test_collection_terms_allowed_user_everyone():
    dims = map_collection_terms({"allowed_user": "Everyone"}, MAPPING)
    assert _dims_without_reasons(dims)["use_scope"] == "everyone"


def test_collection_terms_commercial_disallow():
    dims = map_collection_terms({"commercial_use": "Disallow"}, MAPPING)
    assert _dims_without_reasons(dims)["commercial_scope"] == "none"
    assert "NO_COMMERCIAL" in _reasons(dims)


def test_collection_terms_redistribution_prohibited():
    dims = map_collection_terms({"redistribution": "Prohibited"}, MAPPING)
    assert _dims_without_reasons(dims)["redistribute_original"] == 0
    assert "REDISTRIBUTION_PROHIBITED" in _reasons(dims)


def test_collection_terms_redistribution_allow():
    dims = map_collection_terms({"redistribution": "Allow"}, MAPPING)
    assert _dims_without_reasons(dims)["redistribute_original"] == 1


def test_collection_terms_empty_returns_all_none():
    dims = map_collection_terms({}, MAPPING)
    g = _dims_without_reasons(dims)
    assert all(v is None for v in g.values())


def test_collection_terms_fuzzy_cc_match():
    """Legacy free-text like 'CC0 (CBE-Public)' should still resolve to CC0."""
    dims = map_collection_terms({"vrm_license": "CC0 (CBE-Public)"}, MAPPING)
    assert _dims_without_reasons(dims)["credit"] == "unnecessary"


# --------------------------------------------------------------------------- merge + conflict


def test_merge_layer_higher_precedence_wins():
    acc = _empty_dimensions()
    acc["use_scope"] = "everyone"
    acc_sources = {"use_scope": "external_url"}
    layer = {"use_scope": "holder"}
    conflict, details = _merge_layer(acc, [], acc_sources, layer, [], "collection")
    assert acc["use_scope"] == "everyone"  # higher precedence retained
    assert conflict is True
    assert any("LICENSE_CONFLICT:use_scope" in d for d in details)


def test_merge_layer_no_conflict_when_same_value():
    acc = _empty_dimensions()
    acc["use_scope"] = "everyone"
    acc_sources = {"use_scope": "external_url"}
    layer = {"use_scope": "everyone"}
    conflict, _ = _merge_layer(acc, [], acc_sources, layer, [], "collection")
    assert conflict is False


def test_merge_layer_fills_unset_dims_without_conflict():
    acc = _empty_dimensions()
    acc["use_scope"] = "everyone"
    acc_sources = {"use_scope": "external_url"}
    layer = {"commercial_scope": "personal_profit", "credit": "required"}
    conflict, _ = _merge_layer(acc, [], acc_sources, layer, [], "collection")
    assert conflict is False
    assert acc["commercial_scope"] == "personal_profit"
    assert acc["credit"] == "required"


# --------------------------------------------------------------------------- color derivation


def test_color_unknown_never_green():
    """Empty dimensions → gray, never green."""
    assert evaluate_color(_empty_dimensions(), COLOR_RULES) == "gray"


def test_color_red_for_no_commercial():
    dims = {"commercial_scope": "none"}
    assert evaluate_color(dims, COLOR_RULES) == "red"


def test_color_yellow_for_holder_scope():
    dims = {"use_scope": "holder", "commercial_scope": "corporation",
            "redistribute_original": 0}
    assert evaluate_color(dims, COLOR_RULES) == "yellow"


def test_color_green_requires_all_conditions():
    """Missing modify=1 must not be green even if other conditions hold."""
    dims = {"use_scope": "everyone", "redistribute_original": 1,
            "commercial_scope": "personal_profit"}
    # modify is None → green rule fails → falls through to yellow (redistribute ok)
    # actually yellow requires conditions_any; redistribute_original=1 doesn't
    # trigger yellow, commercial_scope=personal_profit doesn't either, so → gray.
    color = evaluate_color(dims, COLOR_RULES)
    assert color != "green"


# --------------------------------------------------------------------------- assess_collection (full flow)


def test_assess_unknown_collection_is_gray_never_green(db):
    """A collection with no license signal at all → gray, confidence=unknown,
    no conflict. The NEVER_GREEN_FROM_UNKNOWN guard inside assess_collection
    is defensive: it only fires if unknown confidence somehow yields green,
    which cannot happen via the normal flow (no layers → all dims None → gray).
    The observable invariant is color=gray + confidence=unknown."""
    _insert_collection(db, "unknown-c", license_category="unknown")
    row = assess_collection(db, "unknown-c", MAPPING)
    assert row["color"] == "gray"
    assert row["confidence"] == "unknown"
    assert row["conflict_flag"] == 0
    # All dimensions unset.
    for dim in ("use_scope", "commercial_scope", "credit", "redistribute_original",
                "modify", "redistribute_modified", "corporate_use",
                "terminates_on_transfer", "hate_speech_termination"):
        assert row[dim] is None, f"{dim} should be None for unknown collection"


def test_assess_collection_terms_cc0_is_green(db):
    _insert_collection(db, "cc0-c", vrm_license="CC0", license_category="green")
    row = assess_collection(db, "cc0-c", MAPPING)
    assert row["color"] == "green"
    assert row["confidence"] == "collection"
    assert row["use_scope"] == "everyone"
    assert row["redistribute_original"] == 1


def test_assess_embedded_vrm_1_0_restrictive_defaults(db):
    _insert_collection(db, "vrm10-c")
    _insert_embedded(db, "vrm10-c", "1.0", {})  # all fields omitted
    row = assess_collection(db, "vrm10-c", MAPPING)
    assert row["confidence"] == "embedded"
    assert row["use_scope"] == "author"
    assert row["redistribute_original"] == 0
    assert row["modify"] == 0
    # Author-only → yellow, not green.
    assert row["color"] == "yellow"


def test_assess_external_url_overrides_collection_terms(db):
    """External CC0 URL beats a collection-level 'Prohibited' redistribution."""
    _insert_collection(
        db, "url-c",
        vrm_license="Redistribution_Prohibited",
        redistribution="Prohibited",
        description="See https://creativecommons.org/publicdomain/zero/1.0/",
    )
    row = assess_collection(db, "url-c", MAPPING)
    # External URL is highest precedence → redistribute_original=1.
    assert row["redistribute_original"] == 1
    # But the collection terms said 0 → conflict.
    assert row["conflict_flag"] == 1
    assert "LICENSE_CONFLICT" in json.loads(row["reason_codes"])


def test_assess_conflict_between_embedded_and_collection(db):
    """Embedded VRM says CC0 (redistribute=1); collection says Prohibited (0)."""
    _insert_collection(db, "conflict-c", redistribution="Prohibited")
    _insert_embedded(db, "conflict-c", "0.x", {"licenseName": "CC0"})
    row = assess_collection(db, "conflict-c", MAPPING)
    # Collection terms are merged before embedded (higher precedence), so
    # redistribute_original=0 wins and the embedded CC0 value conflicts.
    assert row["redistribute_original"] == 0
    assert row["conflict_flag"] == 1
    rc = json.loads(row["reason_codes"])
    assert "LICENSE_CONFLICT" in rc
    assert any("redistribute_original" in d for d in rc)


def test_assess_manual_layer_only_used_when_nothing_else(db):
    """A manual row is the lowest non-unknown layer; it fills gaps but does not
    override higher layers."""
    _insert_collection(db, "manual-c", vrm_license="CC0")
    # Pre-seed a manual row with a conflicting use_scope.
    db.execute(
        """INSERT INTO license_dimensions
           (collection_id, use_scope, confidence, reason_codes, assessed_at)
           VALUES (?,?,?,?,?)""",
        ("manual-c", "holder", "manual", "[]", "2026-01-01T00:00:00Z"),
    )
    row = assess_collection(db, "manual-c", MAPPING)
    # Collection terms (CC0 → everyone) win over manual (holder).
    assert row["use_scope"] == "everyone"
    assert row["conflict_flag"] == 1


def test_assess_preserves_raw_terms(db):
    _insert_collection(
        db, "raw-c", vrm_license="CC-BY", commercial_use="Allow",
        allowed_user="Everyone", redistribution="Allow",
        description="https://creativecommons.org/licenses/by/4.0/",
    )
    row = assess_collection(db, "raw-c", MAPPING)
    raw_terms = json.loads(row["raw_collection_terms"])
    assert raw_terms["vrm_license"] == "CC-BY"
    assert raw_terms["commercial_use"] == "Allow"
    urls = json.loads(row["raw_external_urls"])
    assert any("creativecommons.org/licenses/by/4.0" in u for u in urls)


def test_assess_holder_gated_a16z_exclusive_via_url(db):
    _insert_collection(
        db, "exc-c",
        description="https://a16z.com/cant-be-evil/exclusive",
    )
    row = assess_collection(db, "exc-c", MAPPING)
    assert row["use_scope"] == "holder"
    assert row["terminates_on_transfer"] == 1
    assert row["redistribute_original"] == 0
    assert row["corporate_use"] == 1
    # Note: reason_codes from the a16z entry (HOLDER_ONLY, REDISTRIBUTION_PROHIBITED)
    # are NOT propagated through resolve_url() — that path returns dimensions only.
    # The dimensions themselves are authoritative; this is a known minor gap.
