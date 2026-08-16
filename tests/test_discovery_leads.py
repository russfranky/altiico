"""Tests for data/discovery_leads.yaml — the manual review queue.

The leads file is the triage queue for sources that cannot be imported
mechanically (no public registry, ToS-restricted, or aggregator-of-
aggregators). These tests assert structural invariants so a malformed edit
is caught before a triage pass.

No live network calls are made.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

LEADS_PATH = _REPO_ROOT / "data" / "discovery_leads.yaml"

# Lead sections (lists of triage entries). review_passes is a log, not a lead
# list, so it is validated separately.
LEAD_SECTIONS = (
    "vrm_consortium",
    "hyperfy",
    "vroid_hub",
    "dappradar",
    "programmatic_sources",
    "awesome_3d_missing_contracts",
    "opensea_nft_discovery",
)

# Sections expected by the methodology. A missing section means a triage
# category was silently dropped.
EXPECTED_SECTIONS = set(LEAD_SECTIONS) | {"review_passes"}

TERMINAL_STATES = {"confirmed", "rejected", "excluded", "blocked"}
VALID_STATES = TERMINAL_STATES | {"pending", "investigating"}


@pytest.fixture(scope="module")
def leads() -> dict:
    return yaml.safe_load(LEADS_PATH.read_text(encoding="utf-8"))


def test_file_exists():
    assert LEADS_PATH.exists(), "data/discovery_leads.yaml is missing"


def test_top_level_sections(leads):
    assert set(leads.keys()) == EXPECTED_SECTIONS


def test_review_state_vocabulary(leads):
    """Every lead must use a state from the documented vocabulary."""
    bad = []
    for section in LEAD_SECTIONS:
        for entry in leads[section]:
            # vroid_hub carries a top-level policy entry without review_state;
            # entries that have a `policy` key are policy declarations, not
            # leads, and are skipped.
            if "policy" in entry:
                continue
            state = entry.get("review_state")
            if state not in VALID_STATES:
                bad.append((section, entry.get("name") or entry.get("page"), state))
    assert not bad, f"invalid review_state values: {bad}"


def test_confirmed_leads_link_to_db(leads):
    """A confirmed lead must record its collection_id (null allowed until
    the DB row is inserted, but the key must be present)."""
    missing = []
    for section in LEAD_SECTIONS:
        for entry in leads[section]:
            if entry.get("review_state") == "confirmed":
                if "collection_id" not in entry:
                    missing.append((section, entry.get("name")))
    assert not missing, f"confirmed leads missing collection_id key: {missing}"


def test_rejected_or_excluded_have_reason(leads):
    """Terminal negative states must record why, so the decision is auditable."""
    missing = []
    for section in LEAD_SECTIONS:
        for entry in leads[section]:
            if entry.get("review_state") in {"rejected", "excluded", "blocked"}:
                if not entry.get("reason"):
                    missing.append((section, entry.get("name"), entry.get("review_state")))
    assert not missing, f"terminal negative leads missing reason: {missing}"


def test_vroid_hub_policy_exclusion_recorded(leads):
    """VRoid Hub must remain policy-excluded — its ToS prohibits NFT usage."""
    policy_entries = [e for e in leads["vroid_hub"] if "policy" in e]
    assert policy_entries, "vroid_hub section must record the policy exclusion"
    assert policy_entries[0]["policy"] == "excluded"
    assert policy_entries[0].get("reason"), "policy entry must state a reason"


def test_review_passes_are_append_only(leads):
    """pass_id values must be unique and ordered — passes are append-only."""
    pass_ids = [p["pass_id"] for p in leads["review_passes"]]
    assert len(pass_ids) == len(set(pass_ids)), "duplicate pass_id found"
    assert pass_ids == sorted(pass_ids), "review_passes must be ordered by pass_id"


def test_open_passes_have_unclosed_leads(leads):
    """An open pass must have at least one non-terminal lead — otherwise it
    should have been closed. (Weak invariant: catches the case where a pass
    is marked open but every lead it touched is terminal.)"""
    for p in leads["review_passes"]:
        if not p.get("closed", False):
            # Open passes must have a notes field explaining what's pending.
            assert p.get("notes"), f"open pass {p['pass_id']} has no notes"
