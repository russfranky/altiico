import json

from scripts.build_openpage_catalog_feed import (
    DEFAULT_API_BASE,
    bind_record,
    binding_index,
    contract_index,
    request_specs,
    request_url,
    research_rows,
    resolve_source_record,
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


def test_invalid_catalog_alias_is_removed_before_other_binding_attempts():
    known, contracts, bindings = indexes()
    row, method, diagnostics = bind_record(
        {"catalog_id": "not-a-catalog-id", "name": "Alpha"},
        known_catalog_ids=known,
        contracts=contracts,
        explicit_bindings=bindings,
    )
    assert "catalogId" not in row
    assert "catalog_id" not in row
    assert "collection_id" not in row
    assert method == "unbound"
    assert diagnostics == ["unknown_catalog_id:not-a-catalog-id", "no_explicit_binding"]


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
    assert report["sourceRefresh"]["requestsConfigured"] == 0
    assert output_path.exists()


def test_current_openpage_api_base_and_documented_metadata_paths():
    assert DEFAULT_API_BASE == "https://api.openpage.fun/v1"
    assert request_url({"kind": "mml", "id": "mml one"}, DEFAULT_API_BASE) == (
        "https://api.openpage.fun/v1/m/mml/mml%20one"
    )
    assert request_url(
        {"kind": "collection_metadata", "id": "collection-1"},
        DEFAULT_API_BASE,
    ) == "https://api.openpage.fun/v1/m/c/collection-1"


def test_request_aliases_expand_and_deduplicate():
    specs = request_specs(
        {
            "mmlId": "mml-1",
            "mmlIds": ["mml-1", "mml-2"],
            "fetchUrls": [
                "https://metadata.test/a.json",
                "https://metadata.test/a.json",
            ],
        }
    )
    assert specs == [
        {"kind": "mml", "id": "mml-1"},
        {"kind": "mml", "id": "mml-2"},
        {"kind": "url", "url": "https://metadata.test/a.json"},
    ]


def test_live_metadata_request_preserves_explicit_binding_and_feeds_candidates(tmp_path):
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
                        "mmlId": "mml-alpha",
                    }
                ]
            }
        )
    )

    calls = []

    def requester(url, api_key, api_base):
        calls.append((url, api_key, api_base))
        return {
            "mml": "<m-character src='https://cdn.test/alpha.vrm'></m-character>",
            "modelUrl": "https://cdn.test/alpha.glb",
        }

    report = run(
        research_path=research_path,
        bindings_path=bindings_path,
        input_paths=[input_path],
        output_path=output_path,
        api_key="secret",
        source_requester=requester,
    )
    assert calls == [
        (
            "https://api.openpage.fun/v1/m/mml/mml-alpha",
            "secret",
            "https://api.openpage.fun/v1",
        )
    ]
    row = report["records"][0]
    assert row["catalogId"] == "alpha"
    assert [item["url"] for item in row["vrmCandidates"]] == [
        "https://cdn.test/alpha.vrm"
    ]
    assert [item["url"] for item in row["glbUrls"]] == [
        "https://cdn.test/alpha.glb"
    ]
    assert row["sourceContext"]["openpageSource"]["kind"] == "mml"
    assert report["sourceRefresh"]["requestsSucceeded"] == 1
    assert report["sourceRefresh"]["requestsFailed"] == 0
    assert report["bindingSummary"]["bound"] == 1


def test_failed_live_request_is_visible_and_does_not_fabricate_assets():
    def requester(url, api_key, api_base):
        raise RuntimeError("upstream unavailable")

    rows, events = resolve_source_record(
        {"catalogId": "alpha", "mmlId": "missing"},
        source_index=3,
        api_base=DEFAULT_API_BASE,
        api_key="secret",
        requester=requester,
    )
    assert len(rows) == 1
    assert rows[0]["catalogId"] == "alpha"
    assert rows[0]["openpageSourceErrors"][0]["status"] == "error"
    assert events[0]["url"] == "https://api.openpage.fun/v1/m/mml/missing"
    assert events[0]["status"] == "error"
    assert "upstream unavailable" in events[0]["error"]


def test_shared_index_fetch_remains_unbound_discovery_only(tmp_path):
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
                        "sourceRecordId": "shared-index",
                        "fetchUrl": "https://docs.openpage.fun/avatars",
                    }
                ]
            }
        )
    )

    def requester(url, api_key, api_base):
        return {"modelUrl": "https://cdn.test/shared-reference.glb"}

    report = run(
        research_path=research_path,
        bindings_path=bindings_path,
        input_paths=[input_path],
        output_path=output_path,
        source_requester=requester,
    )
    row = report["records"][0]
    assert row["catalogId"] is None
    assert [item["url"] for item in row["glbUrls"]] == [
        "https://cdn.test/shared-reference.glb"
    ]
    assert report["bindingSummary"]["bound"] == 0
    assert report["bindingSummary"]["unbound"] == 1
