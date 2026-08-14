from scripts.export_avatar_inventory import infer_format, inventory_for


def base_vrm_row(**updates):
    row = {
        "collection_id": "demo",
        "name": "Demo",
        "state": "unknown",
        "complete": False,
        "terminal": False,
        "expected_models": 2,
        "urls": [],
        "storage": {"types": [], "scope": "vrm_files", "evidence": []},
        "access": {
            "mode": None,
            "requires_ownership": None,
            "access_url": None,
            "evidence": [],
        },
        "inventory_evidence": [],
    }
    row.update(updates)
    return row


def evidence():
    return [{"source": "https://example.test/models", "note": "official avatar files"}]


def test_format_inference_supports_vrm_glb_and_fbx():
    assert infer_format("https://cdn.test/a.vrm?x=1") == "vrm"
    assert infer_format("https://cdn.test/a.glb") == "glb"
    assert infer_format("https://cdn.test/a.fbx#download") == "fbx"


def test_complete_legacy_vrm_inventory_is_still_complete_avatar_inventory():
    row = base_vrm_row(
        state="complete",
        complete=True,
        urls=["https://cdn.test/1.vrm", "https://cdn.test/2.vrm"],
        inventory_evidence=evidence(),
        storage={"types": ["https"], "scope": "vrm_files", "evidence": []},
        access={"mode": "public", "requires_ownership": False, "evidence": []},
    )
    result = inventory_for(row, {})
    assert result["state"] == "complete"
    assert result["coverage_source"] == "complete_vrm_inventory"
    assert result["formats"] == {"vrm": 2}


def test_legacy_vrm_not_shipped_does_not_terminally_rule_out_glb_or_fbx():
    row = base_vrm_row(
        state="not_shipped",
        complete=True,
        terminal=True,
        inventory_evidence=evidence(),
    )
    result = inventory_for(row, {})
    assert result["state"] == "unknown"
    assert result["complete"] is False
    assert result["terminal"] is False


def test_complete_rigged_glb_lane_can_satisfy_avatar_inventory():
    research = {
        "avatar_inventory": {
            "state": "complete",
            "assets": [
                {"url": "https://cdn.test/1.glb", "format": "glb"},
                {"url": "https://cdn.test/2.glb", "format": "glb"},
            ],
            "evidence": evidence(),
        },
        "avatar_file_access": {
            "mode": "public",
            "requires_ownership": False,
            "evidence": evidence(),
        },
    }
    result = inventory_for(base_vrm_row(), research)
    assert result["state"] == "complete"
    assert result["formats"] == {"glb": 2}
    assert result["access"]["mode"] == "public"


def test_fbx_rigging_evidence_is_preserved_for_probe():
    research = {
        "avatar_inventory": {
            "state": "complete",
            "assets": [
                {
                    "url": "https://cdn.test/avatar.fbx",
                    "format": "fbx",
                    "rigged": True,
                    "rigging_evidence": [
                        {"source": "https://example.test/docs", "note": "humanoid rig"}
                    ],
                }
            ],
            "evidence": evidence(),
        }
    }
    result = inventory_for(base_vrm_row(), research)
    asset = result["assets"][0]
    assert asset["format"] == "fbx"
    assert asset["rigged"] is True
    assert asset["rigging_evidence"]
