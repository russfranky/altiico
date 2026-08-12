import json

from scripts.sanitize_staging_provenance import sanitize_staging_provenance


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_collection_level_sample_loses_unproven_nft_identity(tmp_path):
    data = tmp_path / "data"
    write(
        data / "hubzz-prealpha-staging.json",
        {
            "sets": [
                {
                    "set": {"slug": "dickbuttverse", "name": "DickButtVerse"},
                    "sourceAssets": {"path": "hubzz-prealpha-source/dickbuttverse.json"},
                    "sampleEvidence": {
                        "source": "collection-validation",
                        "tokenId": "4326",
                        "canonicalUrl": "https://example.test/0.vrm",
                    },
                }
            ]
        },
    )
    write(
        data / "hubzz-prealpha-source/dickbuttverse.json",
        {
            "avatars": [
                {
                    "id": "4326",
                    "tokenId": "4326",
                    "name": "DickButtVerse #132",
                    "thumbnailUrl": "https://example.test/132.png",
                    "originalSourceUrl": "https://example.test/0.vrm",
                    "validationScope": "collection_sample_binary",
                    "vrmValidated": True,
                }
            ]
        },
    )

    result = sanitize_staging_provenance(data)

    staging = json.loads((data / "hubzz-prealpha-staging.json").read_text())
    sidecar = json.loads((data / "hubzz-prealpha-source/dickbuttverse.json").read_text())
    assert staging["sets"][0]["sampleEvidence"]["tokenId"] is None
    avatar = sidecar["avatars"][0]
    assert avatar["id"] == "sample"
    assert avatar["tokenId"] is None
    assert avatar["name"] == "DickButtVerse sample"
    assert avatar["thumbnailUrl"] is None
    assert avatar["originalSourceUrl"] == "https://example.test/0.vrm"
    assert result == {"setsSanitized": 1, "sidecarFieldsSanitized": 4}


def test_per_avatar_and_recursive_evidence_are_untouched(tmp_path):
    data = tmp_path / "data"
    write(
        data / "hubzz-prealpha-staging.json",
        {
            "sets": [
                {
                    "set": {"slug": "per-token", "name": "Per Token"},
                    "sourceAssets": {"path": "hubzz-prealpha-source/per-token.json"},
                    "sampleEvidence": {"source": "recursive-crawler", "tokenId": "7"},
                }
            ]
        },
    )
    write(
        data / "hubzz-prealpha-source/per-token.json",
        {
            "avatars": [
                {
                    "id": "7",
                    "tokenId": "7",
                    "name": "Per Token #7",
                    "thumbnailUrl": "https://example.test/7.png",
                    "validationScope": "per_avatar_binary",
                }
            ]
        },
    )

    result = sanitize_staging_provenance(data)

    staging = json.loads((data / "hubzz-prealpha-staging.json").read_text())
    sidecar = json.loads((data / "hubzz-prealpha-source/per-token.json").read_text())
    assert staging["sets"][0]["sampleEvidence"]["tokenId"] == "7"
    assert sidecar["avatars"][0]["tokenId"] == "7"
    assert result == {"setsSanitized": 0, "sidecarFieldsSanitized": 0}


def test_missing_staging_is_noop(tmp_path):
    assert sanitize_staging_provenance(tmp_path) == {
        "setsSanitized": 0,
        "sidecarFieldsSanitized": 0,
    }
