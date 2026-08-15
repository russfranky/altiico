import base64

from scripts.enumerate_unity_fbx_avatar_sources import (
    enumerate_source,
    merge_into_research,
    rig_evidence,
)


RIGGED_META = """
ModelImporter:
  humanDescription:
    human:
    - boneName: hips
      humanName: Hips
    skeleton:
    - name: Armature
      parentName:
    - name: hips
      parentName: Armature
  autoGenerateAvatarMappingIfUnspecified: 1
  animationType: 3
  avatarSetup: 1
"""

UNRIGGED_META = """
ModelImporter:
  humanDescription:
    human: []
    skeleton: []
  animationType: 0
  avatarSetup: 0
"""


def blob(text):
    return {
        "encoding": "base64",
        "content": base64.b64encode(text.encode()).decode(),
    }


def requester_for(meta_by_sha, tree_rows, truncated=False):
    def requester(url, token):
        assert token == "token"
        if "/commits/main" in url:
            return {"sha": "commit123", "commit": {"tree": {"sha": "tree123"}}}
        if "/git/trees/tree123?recursive=1" in url:
            return {"tree": tree_rows, "truncated": truncated}
        for sha, text in meta_by_sha.items():
            if url.endswith(f"/git/blobs/{sha}"):
                return blob(text)
        raise AssertionError(url)

    return requester


def test_rig_evidence_requires_explicit_avatar_configuration():
    proof = rig_evidence(RIGGED_META)
    assert proof["rigged"] is True
    assert proof["humanoidMappingCount"] == 1
    assert proof["animationType3"] is True
    assert proof["avatarSetup"] == 1
    assert proof["skeletonEntries"] >= 2

    assert rig_evidence(UNRIGGED_META)["rigged"] is False


def test_untruncated_lane_with_rigged_meta_is_complete():
    tree_rows = [
        {"path": "Assets/Avatar/A.fbx", "type": "blob", "sha": "fbx-a"},
        {"path": "Assets/Avatar/A.fbx.meta", "type": "blob", "sha": "meta-a"},
        {"path": "Assets/Avatar/B.fbx", "type": "blob", "sha": "fbx-b"},
        {"path": "Assets/Avatar/B.fbx.meta", "type": "blob", "sha": "meta-b"},
        {"path": "Assets/Other/prop.fbx", "type": "blob", "sha": "prop"},
    ]
    result = enumerate_source(
        {
            "collection_id": "demo",
            "repo": "owner/repo",
            "ref": "main",
            "root": "Assets/Avatar",
            "public": True,
        },
        requester=requester_for(
            {"meta-a": RIGGED_META, "meta-b": RIGGED_META}, tree_rows
        ),
        token="token",
    )
    assert result["coverage_complete"] is True
    assert result["state"] == "complete"
    assert result["fbx_files"] == 2
    assert result["rigged_avatar_files"] == 2
    assert result["failures"] == []
    assert all(asset["rigged"] is True for asset in result["assets"])
    assert all("commit123" in asset["url"] for asset in result["assets"])


def test_unrigged_or_missing_meta_keeps_lane_partial():
    tree_rows = [
        {"path": "Assets/Avatar/A.fbx", "type": "blob", "sha": "fbx-a"},
        {"path": "Assets/Avatar/A.fbx.meta", "type": "blob", "sha": "meta-a"},
        {"path": "Assets/Avatar/B.fbx", "type": "blob", "sha": "fbx-b"},
        {"path": "Assets/Avatar/B.fbx.meta", "type": "blob", "sha": "meta-b"},
        {"path": "Assets/Avatar/C.fbx", "type": "blob", "sha": "fbx-c"},
    ]
    result = enumerate_source(
        {
            "collection_id": "demo",
            "repo": "owner/repo",
            "root": "Assets/Avatar",
        },
        requester=requester_for(
            {"meta-a": RIGGED_META, "meta-b": UNRIGGED_META}, tree_rows
        ),
        token="token",
    )
    assert result["coverage_complete"] is False
    assert result["state"] == "partial"
    assert result["rigged_avatar_files"] == 1
    assert {row["reason"] for row in result["failures"]} == {
        "rigging_unproven",
        "missing_fbx_meta",
    }


def test_truncated_tree_never_becomes_complete():
    tree_rows = [
        {"path": "Assets/Avatar/A.fbx", "type": "blob", "sha": "fbx-a"},
        {"path": "Assets/Avatar/A.fbx.meta", "type": "blob", "sha": "meta-a"},
    ]
    result = enumerate_source(
        {
            "collection_id": "demo",
            "repo": "owner/repo",
            "root": "Assets/Avatar",
        },
        requester=requester_for({"meta-a": RIGGED_META}, tree_rows, truncated=True),
        token="token",
    )
    assert result["rigged_avatar_files"] == 1
    assert result["coverage_complete"] is False
    assert result["state"] == "partial"


def test_complete_public_lane_materializes_research_and_access():
    research = {"collections": {"demo": {"avatar_inventory": {"state": "partial", "assets": []}}}}
    result = {
        "collection_id": "demo",
        "repo": "owner/repo",
        "commit_sha": "commit123",
        "root": "Assets/Avatar",
        "tree_truncated": False,
        "fbx_files": 1,
        "rigged_avatar_files": 1,
        "coverage_complete": True,
        "state": "complete",
        "public": True,
        "assets": [
            {
                "url": "https://raw.githubusercontent.com/owner/repo/commit123/Assets/Avatar/A.fbx",
                "format": "fbx",
                "rigged": True,
                "rigging_evidence": [{"source": "https://example.test/A.fbx.meta"}],
            }
        ],
    }
    merge_into_research(research, [result])
    row = research["collections"]["demo"]
    assert row["avatar_inventory"]["state"] == "complete"
    assert row["avatar_inventory"]["assets"][0]["rigged"] is True
    assert row["avatar_file_access"]["mode"] == "public"
    assert row["avatar_file_access"]["requires_ownership"] is False
