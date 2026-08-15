from scripts.export_avatars_registry import build_entry


def base_row(**updates):
    row = {
        "id": "demo",
        "name": "Demo",
        "chain": "ethereum",
        "contract": "0x0000000000000000000000000000000000000001",
        "tier": "A",
        "description": "Long description",
        "short_description": "Short description",
        "vrm_license": "All Rights Reserved",
        "license_category": "red",
        "allowed_user": "Holder",
        "redistribution": "Prohibited",
        "vrm_url_pattern": "",
        "vrm_url_https": "",
        "sample_metadata_url": "",
        "vrm_param": "",
        "storage_types": None,
        "file_access_mode": None,
        "file_access_requires_ownership": None,
        "banner_image_url": None,
        "image_url": None,
        "sample_nft_image": None,
        "avatar_count": 1,
    }
    row.update(updates)
    return row


def test_restrictive_license_does_not_imply_holder_gated_download():
    entry, _ = build_entry(base_row())
    assert entry["license"] == "All Rights Reserved"
    assert entry["purchase_gated"] is False


def test_explicit_holder_gating_controls_purchase_gated():
    entry, _ = build_entry(
        base_row(file_access_mode="holder_gated", file_access_requires_ownership=1)
    )
    assert entry["purchase_gated"] is True


def test_explicit_public_access_wins_even_with_restrictive_ip_rights():
    entry, _ = build_entry(
        base_row(file_access_mode="public", file_access_requires_ownership=0)
    )
    assert entry["purchase_gated"] is False


def test_explicit_storage_types_override_legacy_pattern_heuristics():
    entry, _ = build_entry(
        base_row(storage_types='["ipfs"]', vrm_url_pattern="https://cdn.example/{id}.vrm")
    )
    assert entry["storage_provider"] == "ipfs"


def test_short_description_is_public_registry_description():
    entry, _ = build_entry(base_row())
    assert entry["description"] == "Short description"
