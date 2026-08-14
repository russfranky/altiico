import asyncio

from scripts.enumerate_moralis_vrm_inventory import (
    coverage_summary,
    explicit_vrm_urls,
    scan_collection,
)


class FakeMoralis:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    async def collection_nfts(self, chain, contract, *, limit=100, cursor=None):
        self.calls.append((chain, contract, limit, cursor))
        key = cursor or "first"
        return self.pages[key]


def nft(token_id, model_url=None):
    metadata = {"name": f"Avatar #{token_id}"}
    if model_url:
        metadata["model"] = model_url
    return {
        "token_id": str(token_id),
        "token_uri": f"ipfs://metadata/{token_id}.json",
        "normalized_metadata": metadata,
    }


def row(**updates):
    result = {
        "id": "demo",
        "name": "Demo",
        "chain": "ethereum",
        "contract": "0x0000000000000000000000000000000000000001",
        "avatar_count": 3,
        "total_supply": 3,
        "max_supply": 3,
    }
    result.update(updates)
    return result


def test_explicit_vrm_urls_ignores_ordinary_glb_candidates():
    candidate = {
        "metadata": {
            "avatar": "https://cdn.example/avatar.vrm",
            "mesh": "https://cdn.example/avatar.glb",
        }
    }
    assert explicit_vrm_urls(candidate) == ["https://cdn.example/avatar.vrm"]


def test_cursor_exhaustion_with_every_token_link_is_metadata_complete():
    client = FakeMoralis(
        {
            "first": {
                "total": 3,
                "cursor": "next",
                "result": [nft(0, "https://cdn.test/0.vrm"), nft(1, "https://cdn.test/1.vrm")],
            },
            "next": {
                "total": 3,
                "cursor": None,
                "result": [nft(2, "https://cdn.test/2.vrm")],
            },
        }
    )
    result = asyncio.run(scan_collection(client, row()))

    assert result["cursorExhausted"] is True
    assert result["tokensEnumerated"] == 3
    assert result["tokensWithVrmLinks"] == 3
    assert result["tokensMissingVrmLinks"] == 0
    assert result["metadataComplete"] is True
    assert result["vrmUrls"] == [
        "https://cdn.test/0.vrm",
        "https://cdn.test/1.vrm",
        "https://cdn.test/2.vrm",
    ]
    assert [call[3] for call in client.calls] == [None, "next"]


def test_exhausted_cursor_still_fails_when_one_token_has_no_vrm_link():
    client = FakeMoralis(
        {
            "first": {
                "total": 2,
                "cursor": None,
                "result": [nft(0, "https://cdn.test/0.vrm"), nft(1)],
            }
        }
    )
    result = asyncio.run(scan_collection(client, row(avatar_count=2, total_supply=2, max_supply=2)))

    assert result["cursorExhausted"] is True
    assert result["tokensMissingVrmLinks"] == 1
    assert result["metadataComplete"] is False


def test_page_budget_marks_scan_truncated_even_if_scanned_page_is_full():
    client = FakeMoralis(
        {
            "first": {
                "total": 3,
                "cursor": "next",
                "result": [nft(0, "https://cdn.test/0.vrm"), nft(1, "https://cdn.test/1.vrm")],
            },
            "next": {
                "total": 3,
                "cursor": None,
                "result": [nft(2, "https://cdn.test/2.vrm")],
            },
        }
    )
    result = asyncio.run(scan_collection(client, row(), max_pages=1))

    assert result["truncated"] is True
    assert result["cursorExhausted"] is False
    assert result["metadataComplete"] is False


def test_known_supply_prevents_false_complete_when_api_returns_too_few_tokens():
    summary = coverage_summary(
        row=row(avatar_count=10, total_supply=10, max_supply=10),
        tokens=[
            {"tokenId": "0", "vrmUrls": ["https://cdn.test/0.vrm"]},
            {"tokenId": "1", "vrmUrls": ["https://cdn.test/1.vrm"]},
        ],
        cursor_exhausted=True,
        truncated=False,
        api_total=2,
    )
    assert summary["expectedTokens"] == 10
    assert summary["supplyCovered"] is False
    assert summary["metadataComplete"] is False


def test_repeated_cursor_is_error_not_infinite_loop():
    client = FakeMoralis(
        {
            "first": {
                "total": 2,
                "cursor": "again",
                "result": [nft(0, "https://cdn.test/0.vrm")],
            },
            "again": {
                "total": 2,
                "cursor": "again",
                "result": [nft(1, "https://cdn.test/1.vrm")],
            },
        }
    )
    result = asyncio.run(scan_collection(client, row(avatar_count=2, total_supply=2, max_supply=2)))

    assert "repeated cursor" in result["error"]
    assert result["metadataComplete"] is False
