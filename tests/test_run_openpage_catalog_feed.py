import pytest

from scripts.run_openpage_catalog_feed import build_health, validate_community_report


def test_health_counts_only_explicitly_bound_avatar_candidates():
    health = build_health(
        {
            "summary": {
                "communitiesEnumerated": 3,
                "coverageComplete": True,
            }
        },
        {
            "summary": {
                "endpoints": 1,
                "requestsSucceeded": 3,
                "requestsFailed": 0,
                "items": 4,
                "catalogBoundItems": 2,
                "coverageComplete": True,
            }
        },
        {
            "bindingSummary": {"bound": 2, "unbound": 1},
            "records": [
                {
                    "catalogId": "alpha",
                    "vrmCandidates": [{"url": "https://cdn.test/alpha.vrm"}],
                    "glbUrls": [],
                },
                {
                    "catalogId": "alpha",
                    "vrmCandidates": [{"url": "https://cdn.test/alpha.vrm"}],
                    "glbUrls": [{"url": "https://cdn.test/alpha.glb"}],
                },
                {
                    "catalogId": None,
                    "vrmCandidates": [{"url": "https://cdn.test/unbound.vrm"}],
                    "glbUrls": [],
                },
            ],
        },
        {"summary": {"validAvatarUrls": 2}},
    )
    assert health == {
        "schema": "openpage-feed-health-v3",
        "communitiesEnumerated": 3,
        "communityCoverageComplete": True,
        "assetListEndpoints": 1,
        "assetListRequestsSucceeded": 3,
        "assetListRequestsFailed": 0,
        "assetListItems": 4,
        "assetListCatalogBoundItems": 2,
        "assetListCoverageComplete": True,
        "records": 3,
        "boundRecords": 2,
        "boundAssetRecords": 2,
        "boundVrmCandidates": 1,
        "boundGlbCandidates": 1,
        "probeSummary": {"validAvatarUrls": 2},
        "productive": True,
    }


def test_unbound_candidates_do_not_make_feed_productive():
    health = build_health(
        {"summary": {"communitiesEnumerated": 1, "coverageComplete": True}},
        {"summary": {"endpoints": 1, "items": 1}},
        {
            "bindingSummary": {"bound": 0, "unbound": 1},
            "records": [
                {
                    "catalogId": None,
                    "vrmCandidates": [{"url": "https://cdn.test/unbound.vrm"}],
                }
            ],
        },
    )
    assert health["boundVrmCandidates"] == 0
    assert health["productive"] is False


def test_community_report_must_be_nonempty_and_complete():
    with pytest.raises(RuntimeError, match="zero communities"):
        validate_community_report(
            {"summary": {"communitiesEnumerated": 0, "coverageComplete": True}}
        )
    with pytest.raises(RuntimeError, match="incomplete"):
        validate_community_report(
            {"summary": {"communitiesEnumerated": 1, "coverageComplete": False}}
        )
    validate_community_report(
        {"summary": {"communitiesEnumerated": 1, "coverageComplete": True}}
    )
