import pytest

from scripts.run_openpage_catalog_feed import build_health, validate_community_report


def test_health_counts_only_explicitly_bound_and_valid_avatar_candidates():
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
        {
            "summary": {"validAvatarUrls": 2},
            "probes": [
                {
                    "url": "https://cdn.test/alpha.vrm",
                    "validAvatar": True,
                    "actualFormat": "vrm",
                },
                {
                    "url": "https://cdn.test/alpha.glb",
                    "validAvatar": True,
                    "actualFormat": "glb",
                },
                {
                    "url": "https://cdn.test/unbound.vrm",
                    "validAvatar": True,
                    "actualFormat": "vrm",
                },
            ],
        },
    )
    assert health == {
        "schema": "openpage-feed-health-v4",
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
        "boundCandidatesProbed": 2,
        "boundValidAvatarCandidates": 2,
        "boundValidVrmCandidates": 1,
        "boundValidRiggedGlbCandidates": 1,
        "boundInvalidOrUnprobedCandidateUrls": [],
        "candidateDiscoveryProductive": True,
        "validationComplete": True,
        "probeSummary": {"validAvatarUrls": 2},
        "productive": True,
    }


def test_discovered_but_unrigged_candidate_is_not_productive():
    health = build_health(
        {"summary": {"communitiesEnumerated": 1, "coverageComplete": True}},
        {"summary": {"endpoints": 1, "items": 1}},
        {
            "bindingSummary": {"bound": 1, "unbound": 0},
            "records": [
                {
                    "catalogId": "alpha",
                    "glbUrls": [{"url": "https://cdn.test/unrigged.glb"}],
                }
            ],
        },
        {
            "probes": [
                {
                    "url": "https://cdn.test/unrigged.glb",
                    "validAvatar": False,
                    "actualFormat": "glb",
                    "status": "valid_glb_unrigged",
                }
            ]
        },
    )
    assert health["candidateDiscoveryProductive"] is True
    assert health["validationComplete"] is True
    assert health["boundValidAvatarCandidates"] == 0
    assert health["productive"] is False
    assert health["boundInvalidOrUnprobedCandidateUrls"] == [
        "https://cdn.test/unrigged.glb"
    ]


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
        {
            "probes": [
                {
                    "url": "https://cdn.test/unbound.vrm",
                    "validAvatar": True,
                    "actualFormat": "vrm",
                }
            ]
        },
    )
    assert health["boundVrmCandidates"] == 0
    assert health["candidateDiscoveryProductive"] is False
    assert health["productive"] is False


def test_unprobed_bound_candidate_is_not_productive():
    health = build_health(
        {"summary": {"communitiesEnumerated": 1, "coverageComplete": True}},
        {"summary": {"endpoints": 1, "items": 1}},
        {
            "bindingSummary": {"bound": 1},
            "records": [
                {
                    "catalogId": "alpha",
                    "vrmCandidates": [{"url": "https://cdn.test/alpha.vrm"}],
                }
            ],
        },
        {},
    )
    assert health["candidateDiscoveryProductive"] is True
    assert health["validationComplete"] is False
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
