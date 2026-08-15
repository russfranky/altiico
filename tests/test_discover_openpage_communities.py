from scripts.discover_openpage_communities import (
    DEFAULT_API_BASE,
    build_report,
    collect_communities,
    community_page_url,
)


def test_community_page_url_uses_documented_pagination_shape():
    assert DEFAULT_API_BASE == "https://api.openpage.fun/v1"
    assert community_page_url(DEFAULT_API_BASE, 2, 100) == (
        "https://api.openpage.fun/v1/community?page=2&perPage=100"
    )


def test_community_discovery_exhausts_pages_and_deduplicates_ids():
    pages = {
        1: {
            "total": 3,
            "results": [
                {"id": "a", "name": "Alpha", "twitter": "alpha"},
                {"id": "b", "name": "Beta", "discord": "https://discord.gg/beta"},
            ],
        },
        2: {
            "total": 3,
            "results": [
                {"id": "b", "name": "Beta duplicate"},
                {"id": "c", "name": "Gamma", "logo": "https://cdn.test/gamma.png"},
            ],
        },
    }

    def requester(url, api_key):
        assert api_key == "secret"
        page = int(url.split("page=", 1)[1].split("&", 1)[0])
        return pages[page]

    rows, coverage = collect_communities(
        api_base=DEFAULT_API_BASE,
        api_key="secret",
        per_page=2,
        requester=requester,
    )
    assert [row["id"] for row in rows] == ["a", "b", "c"]
    assert coverage == {
        "pages": 2,
        "totalReported": 3,
        "communitiesEnumerated": 3,
        "truncated": False,
        "coverageComplete": True,
    }


def test_page_budget_is_explicitly_truncated():
    def requester(url, api_key):
        return {
            "total": 200,
            "results": [{"id": f"community-{i}"} for i in range(100)],
        }

    rows, coverage = collect_communities(
        api_base=DEFAULT_API_BASE,
        api_key="secret",
        per_page=100,
        max_pages=1,
        requester=requester,
    )
    assert len(rows) == 100
    assert coverage["truncated"] is True
    assert coverage["coverageComplete"] is False


def test_openpage_name_never_auto_binds_catalog_identity():
    report = build_report(
        [
            {
                "id": "community-1",
                "name": "Bored Ape Yacht Club",
                "description": "A community description",
                "twitter": "BoredApeYC",
                "discord": "https://discord.gg/example",
                "website": "https://example.test",
                "logo": "https://example.test/logo.png",
                "bannerUrl": "https://example.test/banner.png",
            }
        ],
        {
            "pages": 1,
            "totalReported": 1,
            "communitiesEnumerated": 1,
            "truncated": False,
            "coverageComplete": True,
        },
        api_base=DEFAULT_API_BASE,
    )
    row = report["communities"][0]
    assert row["name"] == "Bored Ape Yacht Club"
    assert row["catalogId"] is None
    assert row["bindingState"] == "unbound"
    assert row["banner"] == "https://example.test/banner.png"
    assert report["summary"]["withDescription"] == 1
    assert report["summary"]["withX"] == 1
    assert report["summary"]["withDiscord"] == 1
    assert report["summary"]["withBanner"] == 1
