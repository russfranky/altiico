import json

from scripts.build_openpage_catalog_feed import (
    bind_record,
    binding_index,
    contract_index,
    research_rows,
    run,
)


CATALOG = {
    "collections": {
        "alpha": {
            "identity": {
                "name": "Alpha",
                "contract": "0x1111111111111111111111111111111111111111",
            }
        },
        "beta": {
            "identity": {
                "name": "Beta",
                "contract": "0x2222222222222222222222222222222222222222",
            }
        },
    }
}


def indexes(bindings=None):
    research = research_rows(CATALOG)
    return (
        set(research),
        contract_index(research),
        binding_index(bindings or {"bindings": []}, set(research)),
    )


def test_existing_known_catalog_id_is_preserved():
    known, contracts, bindings = indexes()
    row, method, diagnostics = bind_record(
        {"catalogId": "alpha", "modelUrl": "https://cdn.test/a.glb"},
        known_catalog_ids=known,
        contracts=contracts,
        explicit_bindings=bindings,
    )
    assert row["catalogId"] == "alpha"
    assert method == "catalog_id"
    assert diagnostics == []


def test_nested_contract_address_creates_explicit_binding():
    known, contracts, bindings = indexes()
    row, method, diagnostics = bind_record(
        {
            "collection": {
                "contractAddress": "0x1111111111111111111111111111111111111111"
            },
            "modelUrl": "https://cdn.test/a.glb",
        },
        known_catalog_ids=known,
        contracts=contracts,
        explicit_bindings=bindings,
    )
    assert row["catalogId"] == "alpha"
    assert row["catalogBinding"]["method"] == "contract"
    assert method == "contract"
    assert diagnostics == []


def test_display_name_similarity_never_binds():
    known, contracts, bindings = indexes()
    row, method, diagnostics = bind_record(
        {"name": "Alpha", "modelUrl": "https://cdn.test/a.glb"},
        known_catalog_ids=known,
        contracts=contracts,
        explicit_bindings=bindings,
    )
    assert "catalogId" not in row
    assert method == "unbound"
    assert diagnostics == ["no_explicit_binding"]


def test_curated_openpage_id_mapping_binds_without_contract():
    known, contracts, bindings = indexes(
        {"bindings": [{"catalogId": "beta", "openpageId": "op-beta"}]}
    )
    row, method, diagnostics = bind_record(
        {"openpageId": "op-beta", "vrmUrl": "https://cdn.test/b.vrm"},
        known_catalog_ids=known,
        contracts=contracts,
        explicit_bindings=bindings,
    )
    assert row["catalogId"] == "beta"
    assert row["catalogBinding"]["method"] == "openpage_id"
    assert method == "openpage_id"
    assert diagnostics == []


def test_feed_keeps_animation_glb_out_of_avatar_model_candidates(tmp_path):
    research_path = tmp_path / "research.json"
    bindings_path = tmp_path / "bindings.json"
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    research_path.write_text(json.dumps(CATALOG))
    bindings_path.write_text(json.dumps({"bindings": []}))
    input_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "catalogId": "alpha",
                        "modelUrl": "https://cdn.test/avatar.glb",
                        "animationUrl": "https://cdn.test/idle.glb",
                    }
                ]
            }
        )
    )

    report = run(
        research_path=research_path,
        bindings_path=bindings_path,
        input_paths=[input_path],
        output_path=output_path,
    )
    row = report["records"][0]
    assert [item["url"] for item in row["glbUrls"]] == [
        "https://cdn.test/avatar.glb"
    ]
    assert [item["url"] for item in row["animationGlbUrls"]] == [
        "https://cdn.test/idle.glb"
    ]
    assert report["bindingSummary"]["bound"] == 1
    assert output_path.exists()
