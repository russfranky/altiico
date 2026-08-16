from scripts.export_avatar_inventory import infer_format, inventory_for, openpage_asset_index


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


def test_openpage_bound_candidates_feed_avatar_inventory_without_claiming_completeness():
    report = {
        "records": [
            {
                "recordIndex": 4,
                "catalogId": "demo",
                "openpageId": "op-avatar-7",
                "vrmCandidates": [
                    {
                        "url": "https://cdn.test/openpage/avatar.vrm",
                        "source": "$.vrmUrl",
                        "via": "openpage_record",
                    }
                ],
                "glbUrls": [
                    {
                        "url": "https://cdn.test/openpage/avatar.glb",
                        "source": "$.modelUrl",
                        "via": "openpage_record",
                    }
                ],
                "animationGlbUrls": [
                    {
                        "url": "https://cdn.test/openpage/idle.glb",
                        "source": "$.animationUrl",
                        "via": "openpage_record",
                    }
                ],
            }
        ]
    }
    candidates = openpage_asset_index(report)["demo"]
    result = inventory_for(base_vrm_row(), {}, candidates)

    assert result["state"] == "partial"
    assert result["complete"] is False
    assert result["coverage_source"] == "openpage_candidates"
    assert result["formats"] == {"glb": 1, "vrm": 1}
    assert result["urls"] == [
        "https://cdn.test/openpage/avatar.glb",
        "https://cdn.test/openpage/avatar.vrm",
    ]
    assert "https://cdn.test/openpage/idle.glb" not in result["urls"]
    assert all(asset["source_evidence"] for asset in result["assets"])
    assert {
        row["openpage_id"]
        for asset in result["assets"]
        for row in asset["source_evidence"]
    } == {"op-avatar-7"}


def test_openpage_unbound_records_are_never_attached_by_name_or_openpage_id():
    report = {
        "records": [
            {
                "recordIndex": 0,
                "catalogId": None,
                "openpageId": "demo",
                "name": "Demo",
                "vrmCandidates": [
                    {"url": "https://cdn.test/should-not-attach.vrm", "via": "openpage_record"}
                ],
                "glbUrls": [],
                "animationGlbUrls": [
                    {"url": "https://cdn.test/also-ignored.glb", "via": "openpage_record"}
                ],
            }
        ]
    }
    assert openpage_asset_index(report) == {}


def test_openpage_candidates_do_not_override_evidence_backed_terminal_avatar_state():
    terminal_research = {
        "avatar_inventory": {
            "state": "not_shipped",
            "evidence": evidence(),
        }
    }
    candidates = openpage_asset_index(
        {
            "records": [
                {
                    "catalogId": "demo",
                    "vrmCandidates": ["https://cdn.test/conflict.vrm"],
                    "glbUrls": [],
                    "animationGlbUrls": [],
                }
            ]
        }
    )["demo"]
    result = inventory_for(base_vrm_row(), terminal_research, candidates)

    # Discovery candidates are intentionally strong enough to reopen a stale
    # terminal claim, rather than silently coexist with "not shipped".
    assert result["state"] == "partial"
    assert result["complete"] is False
    assert result["terminal"] is False


def test_research_glb_format_overrides_extensionless_vrm_default():
    url = "https://assets.example.test/avatar/3d/abc123"
    row = base_vrm_row(urls=[url])
    research = {
        "avatar_inventory": {
            "state": "partial",
            "assets": [
                {
                    "url": url,
                    "format": "glb",
                    "rigged": False,
                    "source_evidence": [
                        {
                            "kind": "structural_glb_validation",
                            "note": "GLB 2.0 idle, no VRM extension",
                        }
                    ],
                }
            ],
            "evidence": evidence(),
        }
    }
    result = inventory_for(row, research)
    assert result["formats"] == {"glb": 1}
    assert result["assets"][0]["format"] == "glb"
    assert result["assets"][0]["rigged"] is False
