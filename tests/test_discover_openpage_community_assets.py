import json

from scripts.discover_openpage_community_assets import (
    discover_list_endpoints,
    page_url,
    run,
)


OPENAPI = {
    "openapi": "3.0.0",
    "paths": {
        "/community/{id}/file": {
            "get": {
                "operationId": "getCommunityFiles",
                "summary": "Get files",
                "tags": ["Community Files"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "description": "Community ID",
                        "schema": {"type": "string"},
                    },
                    {"name": "page", "in": "query", "schema": {"type": "number"}},
                    {"name": "perPage", "in": "query", "schema": {"type": "number"}},
                ],
            }
        },
        "/community/{id}/file/{fileId}": {
            "get": {
                "operationId": "getCommunityFile",
                "summary": "Get a file",
                "tags": ["Community Files"],
            }
        },
        "/m/mml/{id}": {
            "get": {
                "operationId": "getMmlById",
                "summary": "Get MML by ID",
                "tags": ["Metadata"],
            }
        },
    },
}


def test_openapi_discovers_only_community_asset_list_operations():
    endpoints = discover_list_endpoints(OPENAPI)
    assert endpoints == [
        {
            "kind": "community_files",
            "path": "/community/{id}/file",
            "communityParameter": "id",
            "queryParameters": ["page", "perPage"],
            "operationId": "getCommunityFiles",
            "summary": "Get files",
            "tags": ["Community Files"],
        }
    ]


def test_endpoint_url_uses_discovered_parameter_names():
    endpoint = discover_list_endpoints(OPENAPI)[0]
    assert page_url(
        "https://api.openpage.fun/v1",
        endpoint,
        "community one",
        2,
        100,
    ) == "https://api.openpage.fun/v1/community/community%20one/file?page=2&perPage=100"


def test_run_exhausts_openapi_endpoint_and_preserves_explicit_binding(tmp_path):
    communities = tmp_path / "communities.json"
    bindings = tmp_path / "bindings.json"
    output = tmp_path / "assets.json"
    communities.write_text(
        json.dumps(
            {
                "communities": [
                    {"openpageId": "community-1", "name": "Alpha"},
                    {"openpageId": "community-2", "name": "Unbound"},
                ]
            }
        )
    )
    bindings.write_text(
        json.dumps(
            {
                "bindings": [
                    {"openpageId": "community-1", "catalogId": "alpha"}
                ]
            }
        )
    )

    calls = []

    def requester(url, api_key, api_base):
        calls.append((url, api_key, api_base))
        if url == "https://docs.test/first.json":
            raise RuntimeError("first spec unavailable")
        if url == "https://docs.test/openapi.json":
            return OPENAPI
        if "community-1" in url:
            return {
                "total": 2,
                "page": 1,
                "perPage": 100,
                "results": [
                    {"url": "https://cdn.test/alpha.mml"},
                    {"modelUrl": "https://cdn.test/alpha.glb"},
                ],
            }
        if "community-2" in url:
            return {
                "total": 1,
                "page": 1,
                "perPage": 100,
                "results": [{"vrmUrl": "https://cdn.test/unbound.vrm"}],
            }
        raise AssertionError(url)

    report = run(
        communities_path=communities,
        bindings_path=bindings,
        output_path=output,
        api_base="https://api.openpage.fun/v1",
        api_key="secret",
        openapi_urls=[
            "https://docs.test/first.json",
            "https://docs.test/openapi.json",
        ],
        requester=requester,
    )

    assert report["source"]["openapiUrl"] == "https://docs.test/openapi.json"
    assert report["summary"] == {
        "communities": 2,
        "endpoints": 1,
        "requestsSucceeded": 2,
        "requestsFailed": 0,
        "items": 3,
        "catalogBoundItems": 2,
        "coverageComplete": True,
    }
    alpha_rows = [row for row in report["records"] if row.get("catalogId") == "alpha"]
    assert len(alpha_rows) == 2
    assert {row["openpagePayload"].get("url") or row["openpagePayload"].get("modelUrl") for row in alpha_rows} == {
        "https://cdn.test/alpha.mml",
        "https://cdn.test/alpha.glb",
    }
    unbound = [row for row in report["records"] if row["openpageId"] == "community-2"]
    assert len(unbound) == 1
    assert "catalogId" not in unbound[0]
    assert output.exists()
    assert calls[0][0] == "https://docs.test/first.json"
    assert calls[1][0] == "https://docs.test/openapi.json"


def test_per_community_failure_is_retained_without_fabricating_items(tmp_path):
    communities = tmp_path / "communities.json"
    bindings = tmp_path / "bindings.json"
    output = tmp_path / "assets.json"
    communities.write_text(
        json.dumps({"communities": [{"openpageId": "community-1"}]})
    )
    bindings.write_text(json.dumps({"bindings": []}))

    def requester(url, api_key, api_base):
        if url == "https://docs.test/openapi.json":
            return OPENAPI
        raise RuntimeError("community files forbidden")

    report = run(
        communities_path=communities,
        bindings_path=bindings,
        output_path=output,
        api_base="https://api.openpage.fun/v1",
        api_key="secret",
        openapi_urls=["https://docs.test/openapi.json"],
        requester=requester,
    )
    assert report["summary"]["requestsSucceeded"] == 0
    assert report["summary"]["requestsFailed"] == 1
    assert report["summary"]["items"] == 0
    assert report["summary"]["coverageComplete"] is False
    assert "community files forbidden" in report["errors"][0]["error"]
