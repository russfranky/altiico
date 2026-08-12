from scripts.validate_moralis_candidates import (
    build_candidate_registry,
    expand_results,
    stageable_collection_ids,
    summarize,
)


def test_stageable_collection_ids_reads_staging_shape():
    staging = {
        "sets": [
            {"set": {"slug": "already-ready"}},
            {"set": {"slug": "another-ready"}},
        ]
    }
    assert stageable_collection_ids(staging) == {"already-ready", "another-ready"}


def test_candidate_registry_skips_stageable_and_dedupes_supported_models():
    report = {
        "collections": [
            {
                "catalogId": "already-ready",
                "name": "Ready",
                "chain": "ethereum",
                "contract": "0xready",
                "nfts": [
                    {
                        "tokenId": "1",
                        "modelCandidates": [
                            {"path": "$.vrm", "url": "https://example.com/ready.vrm"}
                        ],
                    }
                ],
            },
            {
                "catalogId": "deferred",
                "name": "Deferred",
                "chain": "ethereum",
                "contract": "0xdeferred",
                "nfts": [
                    {
                        "tokenId": "7",
                        "unsupportedMedia": True,
                        "tokenUri": "ipfs://meta/7",
                        "modelCandidates": [
                            {"path": "$.vrm", "url": "https://example.com/avatar.vrm"},
                            {"path": "$.description", "url": "https://example.com/avatar.vrm"},
                            {"path": "$.animation_url", "url": "ipfs://cid/model.glb"},
                            {"path": "$.other", "url": "https://example.com/model.gltf"},
                        ],
                    }
                ],
            },
        ]
    }

    candidates, stats = build_candidate_registry(report, {"already-ready"})

    assert [row["canonical_url"] for row in candidates] == [
        "https://example.com/avatar.vrm",
        "ipfs://cid/model.glb",
    ]
    assert len(candidates[0]["bindings"]) == 1
    assert candidates[0]["bindings"][0]["catalogId"] == "deferred"
    assert candidates[0]["bindings"][0]["tokenId"] == "7"
    assert stats["uniqueCandidateUrls"] == 2
    assert stats["skippedStageableCollections"] == 1
    assert stats["skippedUnsupportedSuffixes"] == 1


def test_expand_results_emits_promotion_ready_shape_only_from_binary_proof():
    audited = [
        {
            "candidate": {
                "canonical_url": "ipfs://cid/avatar.vrm",
                "bindings": [
                    {
                        "catalogId": "deferred",
                        "collectionId": "deferred",
                        "name": "Deferred",
                        "chain": "ethereum",
                        "contract": "0xabc",
                        "tokenId": "9",
                        "tokenUri": "ipfs://meta/9",
                        "modelUrl": "ipfs://cid/avatar.vrm",
                        "sourcePath": "$.vrm_url",
                        "unsupportedMedia": False,
                    }
                ],
            },
            "validation": {
                "status": "valid_vrm",
                "vrm_spec": "1.0",
                "content_sha256": "a" * 64,
                "observed_length": 1234,
                "transport_url": "https://gateway.example/ipfs/cid/avatar.vrm",
                "json_chunk_sha256": "b" * 64,
                "attempts": 1,
                "error": "",
            },
            "errors": [],
        }
    ]

    results = expand_results(audited, "2026-08-12T00:00:00+00:00")

    assert results == [
        {
            "catalogId": "deferred",
            "collectionId": "deferred",
            "name": "Deferred",
            "chain": "ethereum",
            "contract": "0xabc",
            "tokenId": "9",
            "tokenUri": "ipfs://meta/9",
            "modelUrl": "ipfs://cid/avatar.vrm",
            "sourcePath": "$.vrm_url",
            "unsupportedMedia": False,
            "source": "moralis_model_discovery",
            "observedAt": "2026-08-12T00:00:00+00:00",
            "canonical_url": "ipfs://cid/avatar.vrm",
            "status": "valid_vrm",
            "validation_status": "valid_vrm",
            "vrm_spec": "1.0",
            "sha256": "a" * 64,
            "byte_length": 1234,
            "transport_url": "https://gateway.example/ipfs/cid/avatar.vrm",
            "json_chunk_sha256": "b" * 64,
            "validation_error": None,
            "validation_attempts": 1,
            "validation_errors": [],
        }
    ]
    summary = summarize(
        results,
        {
            "uniqueCandidateUrls": 1,
            "candidateBindings": 1,
            "skippedStageableCollections": 0,
            "skippedUnsupportedSuffixes": 0,
            "invalidCandidateUris": 0,
        },
        1,
    )
    assert summary["validatedVrms"] == 1
    assert summary["collectionsWithValidatedVrms"] == 1
    assert summary["validatedBytes"] == 1234
