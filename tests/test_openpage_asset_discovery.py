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


def test_direct_openpage_vrm_is_candidate_not_validation():
    report = build_report(
        [
            {
                "catalogId": "demo",
                "vrmUrl": "https://cdn.example/avatar.vrm?version=4",
                "animationUrl": "https://cdn.example/avatar.glb",
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
    assert "candidates only" in report["policy"]
    assert report["summary"]["uniqueVrmCandidates"] == 1


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
