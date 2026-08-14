import json
from pathlib import Path

from scripts.enforce_catalog_acceptance import evaluate_collection, run


def field(value=None, ok=True, state="present"):
    out = {"ok": ok, "state": state}
    if value is not None:
        out["value"] = value
    return out


def complete_collection():
    return {
        "id": "demo",
        "name": "Demo",
        "fields": {
            "banner": field("https://example.test/banner.png"),
            "short_description": field("A useful short collection description."),
            "discord": field("https://discord.gg/demo"),
            "x": field("https://x.com/demo"),
            "logo": field("https://example.test/logo.png"),
            "launch_date": field("2024-01-02"),
            "ip_rights": field({"summary": "CC0"}),
            "project_status": field("active"),
        },
    }


def complete_inventory():
    return {
        "collection_id": "demo",
        "state": "complete",
        "complete": True,
        "urls": ["ipfs://bafy/1.vrm", "ipfs://bafy/2.vrm"],
        "storage": {"types": ["ipfs"], "scope": "vrm_files", "evidence": []},
        "inventory_evidence": [],
        "access": {
            "mode": "public",
            "requires_ownership": False,
            "evidence": [],
        },
    }


def complete_probe():
    return {
        "catalogId": "demo",
        "metadataComplete": True,
        "structurallyComplete": True,
        "urls": 2,
        "validVrmUrls": 2,
        "invalidUrls": [],
    }


def test_actual_media_and_social_values_are_required_even_if_negative_state_is_researched():
    collection = complete_collection()
    collection["fields"]["banner"] = field(ok=True, state="not_available")
    collection["fields"]["discord"] = field(ok=True, state="not_available")
    failures = evaluate_collection(collection, complete_inventory(), complete_probe())
    assert "banner:actual_value_required" in failures
    assert "discord:actual_value_required" in failures


def test_storage_must_have_actual_type_on_final_inventory():
    inventory = complete_inventory()
    inventory["storage"]["types"] = []
    failures = evaluate_collection(complete_collection(), inventory, complete_probe())
    assert "storage:actual_storage_type_required" in failures


def test_public_file_access_must_explicitly_answer_ownership_requirement():
    inventory = complete_inventory()
    inventory["access"]["requires_ownership"] = None
    failures = evaluate_collection(complete_collection(), inventory, complete_probe())
    assert "file_access:ownership_requirement_boolean_required" in failures


def test_holder_gated_access_must_require_ownership():
    inventory = complete_inventory()
    inventory["access"] = {
        "mode": "holder_gated",
        "requires_ownership": False,
        "evidence": [{"source": "https://example.test/access"}],
    }
    failures = evaluate_collection(complete_collection(), inventory, complete_probe())
    assert "file_access:holder_gated_must_require_ownership" in failures


def test_nonterminal_inventory_requires_structural_probe_for_every_link():
    failures = evaluate_collection(complete_collection(), complete_inventory(), None)
    assert "vrm_inventory:all_links_must_probe_as_vrm" in failures
    bad_probe = complete_probe()
    bad_probe["structurallyComplete"] = False
    failures = evaluate_collection(complete_collection(), complete_inventory(), bad_probe)
    assert "vrm_inventory:all_links_must_probe_as_vrm" in failures


def test_unexpanded_template_does_not_satisfy_all_links():
    inventory = complete_inventory()
    inventory.update(
        {
            "state": "complete_template",
            "complete": True,
            "urls": [],
            "candidate_url_template": "ipfs://bafy/{id}.vrm",
        }
    )
    failures = evaluate_collection(complete_collection(), inventory, complete_probe())
    assert "vrm_inventory:explicit_exhaustive_links_required" in failures


def test_terminal_unrecoverable_inventory_can_be_complete_with_evidence_and_unavailable_access():
    inventory = {
        "collection_id": "demo",
        "state": "unrecoverable",
        "complete": True,
        "terminal": True,
        "urls": [],
        "storage": {
            "types": ["ipfs"],
            "scope": "nft_metadata_and_images",
            "evidence": [{"source": "archive"}],
        },
        "inventory_evidence": [
            {"source": "archive", "note": "no recoverable model refs"}
        ],
        "access": {
            "mode": "unavailable",
            "requires_ownership": None,
            "evidence": [{"source": "archive", "note": "no accessible file"}],
        },
    }
    failures = evaluate_collection(complete_collection(), inventory)
    assert failures == []


def test_holder_gated_is_not_a_terminal_no_link_escape():
    inventory = {
        "collection_id": "demo",
        "state": "holder_gated",
        "complete": True,
        "terminal": True,
        "urls": [],
        "storage": {"types": ["https"], "scope": "vrm_files", "evidence": []},
        "inventory_evidence": [{"source": "holder portal"}],
        "access": {
            "mode": "holder_gated",
            "requires_ownership": True,
            "evidence": [{"source": "holder portal"}],
        },
    }
    failures = evaluate_collection(complete_collection(), inventory)
    assert "vrm_inventory:explicit_exhaustive_links_required" in failures


def test_terminal_inventory_without_evidence_fails():
    inventory = {
        "collection_id": "demo",
        "state": "unrecoverable",
        "complete": True,
        "terminal": True,
        "urls": [],
        "storage": {"types": ["ipfs"], "scope": "nft_metadata", "evidence": []},
        "inventory_evidence": [],
        "access": {
            "mode": "unavailable",
            "requires_ownership": None,
            "evidence": [],
        },
    }
    failures = evaluate_collection(complete_collection(), inventory)
    assert "vrm_inventory:terminal_state_requires_evidence" in failures
    assert "file_access:unavailable_requires_evidence" in failures


def test_run_uses_probe_and_fails_collection_when_literal_requirement_missing(tmp_path: Path):
    report = tmp_path / "report.json"
    inventory = tmp_path / "inventory.json"
    probe = tmp_path / "probe.json"
    collection = complete_collection()
    collection["fields"]["x"] = field(ok=True, state="not_available")
    report.write_text(json.dumps({"collections": [collection]}), encoding="utf-8")
    inventory.write_text(json.dumps({"collections": [complete_inventory()]}), encoding="utf-8")
    probe.write_text(json.dumps({"collections": [complete_probe()]}), encoding="utf-8")

    result = run(report, inventory, probe)

    assert result["collections"] == 1
    assert result["passing"] == 0
    assert result["failing"] == 1
    assert result["reasonCounts"]["x:actual_value_required"] == 1


def test_scope_source_collection_cannot_disappear_from_acceptance_denominator(tmp_path: Path):
    report = tmp_path / "report.json"
    inventory = tmp_path / "inventory.json"
    probe = tmp_path / "probe.json"
    scope = tmp_path / "vrm_collections.md"

    report.write_text(
        json.dumps({"collections": [complete_collection()]}), encoding="utf-8"
    )
    inventory.write_text(
        json.dumps({"collections": [complete_inventory()]}), encoding="utf-8"
    )
    probe.write_text(
        json.dumps({"collections": [complete_probe()]}), encoding="utf-8"
    )
    scope.write_text(
        """
## Tier C — historical collection leads

### Ethereum mainnet

| Collection | Contract | OpenSea slug | Notes |
| --- | --- | --- | --- |
| Demo | `0x1111111111111111111111111111111111111111` | demo | Already represented |
| Missing Sergs | `0x2222222222222222222222222222222222222222` | missing-sergs | Must not vanish |
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run(report, inventory, probe, scope)

    assert result["reportCollections"] == 1
    assert result["scopeCollections"] == 2
    assert result["scopeMissing"] == 1
    assert result["collections"] == 2
    assert result["passing"] == 1
    assert result["failing"] == 1
    assert result["reasonCounts"]["catalog_scope:missing_from_completeness_report"] == 1
    assert result["failures"][0]["id"] == "missing-sergs"
