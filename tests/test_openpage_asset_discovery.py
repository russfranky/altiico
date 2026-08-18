from scripts.openpage_asset_discovery import build_report, inspect_record, record_list


def test_mml_url_alone_never_becomes_vrm_candidate():
    result = inspect_record(
        {
            "catalogId": "demo",
            "mmlUrl": "https://assets.openpage.fun/avatar/42.mml",
        }
    )
    assert [row["url"] for row in result["mmlUrls"]] == [
        "https://assets.openpage.fun/avatar/42.mml"
    ]
    assert result["vrmCandidates"] == []
    assert result["glbUrls"] == []
    assert result["animationGlbUrls"] == []


def test_generic_mml_extension_is_classified_without_a_typed_field():
    result = inspect_record(
        {
            "catalogId": "demo",
            "download": "https://assets.openpage.fun/avatar/42.mml?version=2",
        }
    )
    assert [row["url"] for row in result["mmlUrls"]] == [
        "https://assets.openpage.fun/avatar/42.mml?version=2"
    ]


def test_typed_fields_classify_opaque_cdn_urls():
    result = inspect_record(
        {
            "catalogId": "demo",
            "mmlUrl": "https://cdn.example/file/one",
            "vrmUrl": "https://cdn.example/file/two",
            "modelUrl": "https://cdn.example/file/three",
            "animationUrl": "https://cdn.example/file/four",
        }
    )
    assert [row["url"] for row in result["mmlUrls"]] == [
        "https://cdn.example/file/one"
    ]
    assert [row["url"] for row in result["vrmCandidates"]] == [
        "https://cdn.example/file/two"
    ]
    assert [row["url"] for row in result["glbUrls"]] == [
        "https://cdn.example/file/three"
    ]
    assert [row["url"] for row in result["animationGlbUrls"]] == [
        "https://cdn.example/file/four"
    ]


def test_direct_openpage_vrm_and_model_glb_are_candidates_but_animation_glb_is_not():
    report = build_report(
        [
            {
                "catalogId": "demo",
                "vrmUrl": "https://cdn.example/avatar.vrm?version=4",
                "modelUrl": "https://cdn.example/avatar.glb",
                "animationUrl": "https://cdn.example/idle.glb",
            }
        ]
    )
    row = report["records"][0]
    assert [item["url"] for item in row["vrmCandidates"]] == [
        "https://cdn.example/avatar.vrm?version=4"
    ]
    assert [item["url"] for item in row["glbUrls"]] == [
        "https://cdn.example/avatar.glb"
    ]
    assert [item["url"] for item in row["animationGlbUrls"]] == [
        "https://cdn.example/idle.glb"
    ]
    assert "candidates only" in report["policy"]
    assert report["summary"]["uniqueVrmCandidates"] == 1
    assert report["summary"]["uniqueGlbCandidates"] == 1
    assert report["summary"]["uniqueAnimationGlbs"] == 1


def test_named_animation_glb_is_not_model_candidate_even_in_generic_field():
    result = inspect_record(
        {
            "catalogId": "boredapeyachtclub",
            "download": "https://example.test/bayc-animations.glb",
        }
    )
    assert result["glbUrls"] == []
    assert [item["url"] for item in result["animationGlbUrls"]] == [
        "https://example.test/bayc-animations.glb"
    ]


def test_inline_mml_keeps_glb_separate_from_vrm():
    result = inspect_record(
        {
            "catalogId": "demo",
            "mml": """
                <m-character src="https://cdn.example/base.glb"></m-character>
                <m-model src='https://cdn.example/prop.gltf'></m-model>
            """,
        }
    )
    assert result["vrmCandidates"] == []
    assert {item["url"] for item in result["glbUrls"]} == {
        "https://cdn.example/base.glb",
        "https://cdn.example/prop.gltf",
    }
    assert result["animationGlbUrls"] == []


def test_inline_mml_can_surface_explicit_vrm_candidate():
    result = inspect_record(
        {
            "catalogId": "demo",
            "mml": '<m-character src="https://cdn.example/avatar.vrm"></m-character>',
        }
    )
    assert result["vrmCandidates"] == [
        {
            "url": "https://cdn.example/avatar.vrm",
            "source": "$.mml",
            "via": "mml_inline",
        }
    ]


def test_inline_mml_upgrades_weaker_openpage_record_for_same_url():
    result = inspect_record(
        {
            "catalogId": "demo",
            "vrmUrl": "https://cdn.example/avatar.vrm",
            "mml": '<m-character src="https://cdn.example/avatar.vrm"></m-character>',
        }
    )
    assert result["vrmCandidates"] == [
        {
            "url": "https://cdn.example/avatar.vrm",
            "source": "$.mml",
            "via": "mml_inline",
        }
    ]


def test_fetched_mml_resolves_relative_model_src_without_promoting_glb():
    def fake_fetch(url):
        assert url == "https://assets.openpage.fun/avatar/42.mml"
        return """
            <m-character src="../models/avatar.vrm"></m-character>
            <m-model src="../models/avatar.glb"></m-model>
        """

    result = inspect_record(
        {
            "catalogId": "demo",
            "mmlUrl": "https://assets.openpage.fun/avatar/42.mml",
        },
        fetch_mml=True,
        fetcher=fake_fetch,
    )
    assert {item["url"] for item in result["vrmCandidates"]} == {
        "https://assets.openpage.fun/models/avatar.vrm"
    }
    assert {item["url"] for item in result["glbUrls"]} == {
        "https://assets.openpage.fun/models/avatar.glb"
    }
    assert result["fetchErrors"] == []


def test_fetched_json_keeps_animation_field_out_of_model_candidates():
    def fake_fetch(url):
        assert url == "https://assets.openpage.fun/avatar/42.mml"
        return """{
          "modelUrl": "https://cdn.example/avatar.glb",
          "animationUrl": "https://cdn.example/talking.glb"
        }"""

    result = inspect_record(
        {
            "catalogId": "demo",
            "mmlUrl": "https://assets.openpage.fun/avatar/42.mml",
        },
        fetch_mml=True,
        fetcher=fake_fetch,
    )
    assert [item["url"] for item in result["glbUrls"]] == [
        "https://cdn.example/avatar.glb"
    ]
    assert [item["url"] for item in result["animationGlbUrls"]] == [
        "https://cdn.example/talking.glb"
    ]


def test_duplicate_urls_are_deduplicated_per_evidence_lane():
    result = inspect_record(
        {
            "catalogId": "demo",
            "vrmUrl": "https://cdn.example/avatar.vrm",
            "files": {"vrm": "https://cdn.example/avatar.vrm"},
        }
    )
    assert len(result["vrmCandidates"]) == 1


def test_generic_export_wrappers_are_accepted():
    payload = {
        "avatars": [
            {"id": "a", "vrmUrl": "https://cdn.example/a.vrm"},
            {"id": "b", "vrmUrl": "https://cdn.example/b.vrm"},
        ]
    }
    rows = record_list(payload)
    assert [row["id"] for row in rows] == ["a", "b"]


def test_openpage_community_report_wrapper_is_accepted():
    payload = {
        "schema": "openpage-community-discovery-v1",
        "communities": [
            {"openpageId": "community-a", "name": "Alpha"},
            {"openpageId": "community-b", "name": "Beta"},
        ],
    }
    rows = record_list(payload)
    assert [row["openpageId"] for row in rows] == ["community-a", "community-b"]
