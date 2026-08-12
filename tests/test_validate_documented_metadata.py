from scripts import validate_documented_metadata as documented


REGISTRY = """
| Creator | Contract | Metadata | Metadata Param | Preview | VRM |
| --- | --- | --- | --- | --- | --- |
| [Cyberbrokers Genesis Mechs](https://example.test/) | [Link](https://etherscan.io/address/0xb286ac8eff9f44e2c377c6770cad5fc78bff9ed6) | [Link](https://example.test/meta/1) | VRM: `vrm_url` / GLB `files:glb` | x | ✔️ |
| [No Pointer](https://example.test/) | [Link](https://etherscan.io/address/0x1111111111111111111111111111111111111111) | [Link](https://example.test/meta/2) | No metadata for 3D avatar file | x | ✔️ |
| [Missing Metadata](https://example.test/) | [Link](https://etherscan.io/address/0x2222222222222222222222222222222222222222) | N/A | VRM: `vrm_url` | x | ✔️ |
"""


def test_parse_registry_requires_explicit_vrm_field_and_metadata_link():
    rows = documented.parse_registry(REGISTRY)
    assert rows == [
        {
            "registryName": "Cyberbrokers Genesis Mechs",
            "contract": "0xb286ac8eff9f44e2c377c6770cad5fc78bff9ed6",
            "metadataUrl": "https://example.test/meta/1",
            "metadataParam": "VRM: `vrm_url` / GLB `files:glb`",
        }
    ]


def test_select_targets_requires_exact_contract_and_skips_stageable():
    rows = documented.parse_registry(REGISTRY)
    contract = rows[0]["contract"]
    catalog = {
        contract: {
            "id": "cyberbrokers",
            "name": "CyberBrokers",
            "chain": "ethereum",
            "contract": contract,
        }
    }

    targets, summary = documented.select_targets(rows, catalog, set())
    assert targets[0]["catalogId"] == "cyberbrokers"
    assert targets[0]["contract"] == contract
    assert summary == {
        "registryRowsWithExplicitVrmField": 1,
        "skippedAlreadyStageable": 0,
        "skippedMissingExactCatalogIdentity": 0,
        "selectedTargets": 1,
    }

    targets, summary = documented.select_targets(rows, catalog, {contract})
    assert targets == []
    assert summary["skippedAlreadyStageable"] == 1


def test_select_targets_never_fuzzy_matches_names():
    rows = documented.parse_registry(REGISTRY)
    targets, summary = documented.select_targets(
        rows,
        {
            "0x3333333333333333333333333333333333333333": {
                "id": "cyberbrokers",
                "name": "Cyberbrokers Genesis Mechs",
                "chain": "ethereum",
                "contract": "0x3333333333333333333333333333333333333333",
            }
        },
        set(),
    )
    assert targets == []
    assert summary["skippedMissingExactCatalogIdentity"] == 1


def test_stageable_contracts_uses_chain_and_contract_identity():
    staging = {
        "sets": [
            {
                "set": {
                    "slug": "one",
                    "chain": "ethereum",
                    "contract": "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                }
            },
            {
                "set": {
                    "slug": "two",
                    "chain": "polygon",
                    "contract": "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
                }
            },
        ]
    }
    assert documented.stageable_contracts(staging) == {
        "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }


def test_inspect_target_deduplicates_and_binary_validates(monkeypatch):
    monkeypatch.setattr(
        documented,
        "fetch_metadata",
        lambda url, timeout: {
            "vrm_url": "https://assets.example/avatar.vrm",
            "nested": {"asset": "https://assets.example/avatar.vrm"},
        },
    )
    calls = []

    def fake_validate(url, policy, max_attempts):
        calls.append(url)
        return {
            "url": url,
            "canonicalUrl": url,
            "status": "valid_vrm",
            "vrmSpec": "1.0",
            "contentSha256": "a" * 64,
            "byteLength": 1234,
        }

    monkeypatch.setattr(documented, "validate_pointer", fake_validate)
    target = {
        "registryName": "Example",
        "contract": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "metadataUrl": "https://example.test/meta/1",
        "metadataParam": "VRM: `vrm_url`",
        "catalogId": "example",
        "catalogName": "Example",
    }
    result = documented.inspect_target(target, policy=object(), timeout=1.0, max_attempts=2)
    assert result["metadataFetch"] == "ok"
    assert calls == ["https://assets.example/avatar.vrm"]
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["status"] == "valid_vrm"

    summary = documented.summarize(
        [result],
        {
            "registryRowsWithExplicitVrmField": 1,
            "skippedAlreadyStageable": 0,
            "skippedMissingExactCatalogIdentity": 0,
            "selectedTargets": 1,
        },
    )
    assert summary["validatedVrms"] == 1
    assert summary["collectionsWithValidatedVrms"] == 1
    assert summary["validatedBytes"] == 1234


def test_metadata_fetch_failure_is_reported_not_promoted(monkeypatch):
    def fail(url, timeout):
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(documented, "fetch_metadata", fail)
    target = {
        "registryName": "Example",
        "contract": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "metadataUrl": "https://example.test/meta/1",
        "metadataParam": "VRM: `vrm_url`",
        "catalogId": "example",
        "catalogName": "Example",
    }
    result = documented.inspect_target(target, policy=object(), timeout=1.0, max_attempts=2)
    assert result["metadataFetch"] == "error"
    assert result["candidates"] == []
    assert "metadata unavailable" in result["metadataError"]
