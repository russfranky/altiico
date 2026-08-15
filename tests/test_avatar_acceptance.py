from scripts.enforce_avatar_acceptance import evaluate_collection


def field(value=None, ok=True, state="present"):
    out = {"ok": ok, "state": state}
    if value is not None:
        out["value"] = value
    return out


def collection():
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


def inventory(fmt="glb"):
    return {
        "collection_id": "demo",
        "state": "complete",
        "complete": True,
        "assets": [{"url": f"https://cdn.test/avatar.{fmt}", "format": fmt}],
        "storage": {"types": ["https"], "scope": "avatar_files", "evidence": []},
        "inventory_evidence": [{"source": "https://example.test/models"}],
        "access": {
            "mode": "public",
            "requires_ownership": False,
            "evidence": [],
        },
    }


def test_rigged_glb_probe_can_satisfy_final_acceptance():
    failures = evaluate_collection(
        collection(),
        inventory("glb"),
        {"catalogId": "demo", "avatarReadyComplete": True},
    )
    assert failures == []


def test_evidence_backed_fbx_probe_can_satisfy_final_acceptance():
    failures = evaluate_collection(
        collection(),
        inventory("fbx"),
        {"catalogId": "demo", "avatarReadyComplete": True},
    )
    assert failures == []


def test_unrigged_or_unproven_asset_fails_even_with_complete_inventory_claim():
    failures = evaluate_collection(
        collection(),
        inventory("glb"),
        {"catalogId": "demo", "avatarReadyComplete": False},
    )
    assert "avatar_inventory:all_assets_must_be_avatar_ready" in failures


def test_terminal_avatar_state_requires_broader_evidence():
    terminal = {
        "collection_id": "demo",
        "state": "not_shipped",
        "complete": True,
        "terminal": True,
        "assets": [],
        "storage": {"types": ["https"], "scope": "historical_project_assets"},
        "inventory_evidence": [{"source": "official archive", "note": "no usable avatar files shipped"}],
        "access": {
            "mode": "unavailable",
            "requires_ownership": None,
            "evidence": [{"source": "official archive"}],
        },
    }
    assert evaluate_collection(collection(), terminal, None) == []
