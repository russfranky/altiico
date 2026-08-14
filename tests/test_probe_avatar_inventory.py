import json
import struct
from types import SimpleNamespace

from scripts.crawler.fetch import GLB_MAGIC, GLB_VERSION_2, JSON_CHUNK_TYPE
from scripts.crawler.models import CrawlPolicy
from scripts.probe_avatar_inventory import collection_probe_summary, probe_asset


def policy():
    return CrawlPolicy(
        max_depth=0,
        request_budget=100,
        max_tasks=100,
        max_attempts=1,
        timeout=1,
        max_document_bytes=1024 * 1024,
        max_vrm_json_bytes=1024 * 1024,
        max_vrm_bytes=8 * 1024 * 1024,
        max_links_per_document=0,
    )


def glb_json(payload):
    body = json.dumps(payload).encode()
    while len(body) % 4:
        body += b" "
    total = 20 + len(body)
    return (
        struct.pack("<III", GLB_MAGIC, GLB_VERSION_2, total)
        + struct.pack("<II", len(body), JSON_CHUNK_TYPE)
        + body
    )


class FakeLoader:
    def __init__(self, blob):
        self.blob = blob

    def fetch_range(self, url, start, end, *, preferred_transport=None):
        return SimpleNamespace(
            body=self.blob[start : end + 1],
            network_requests=1,
            final_url=url,
        )


def test_vrm_remains_valid_avatar():
    blob = glb_json(
        {
            "asset": {"version": "2.0"},
            "extensions": {"VRMC_vrm": {"specVersion": "1.0"}},
        }
    )
    result = probe_asset(
        {"url": "https://cdn.test/a.vrm", "format": "vrm"},
        policy(),
        loader=FakeLoader(blob),
    )
    assert result["validAvatar"] is True
    assert result["validVrm"] is True
    assert result["actualFormat"] == "vrm"


def test_rigged_glb_with_skin_and_joints_is_valid_avatar():
    blob = glb_json(
        {
            "asset": {"version": "2.0"},
            "nodes": [{}, {}, {}],
            "meshes": [{"primitives": []}],
            "skins": [{"joints": [0, 1, 2]}],
        }
    )
    result = probe_asset(
        {"url": "https://cdn.test/a.glb", "format": "glb"},
        policy(),
        loader=FakeLoader(blob),
    )
    assert result["validAvatar"] is True
    assert result["validVrm"] is False
    assert result["status"] == "valid_rigged_glb"
    assert result["actualFormat"] == "glb"


def test_plain_unrigged_glb_is_rejected_as_avatar():
    blob = glb_json(
        {
            "asset": {"version": "2.0"},
            "nodes": [{}],
            "meshes": [{"primitives": []}],
        }
    )
    result = probe_asset(
        {"url": "https://cdn.test/a.glb", "format": "glb"},
        policy(),
        loader=FakeLoader(blob),
    )
    assert result["validAvatar"] is False
    assert result["status"] == "valid_glb_unrigged"


def test_fbx_requires_both_real_fbx_bytes_and_rigging_evidence():
    blob = b"Kaydara FBX Binary  \x00\x1a\x00" + b"\x00" * 128
    evidenced = probe_asset(
        {
            "url": "https://cdn.test/avatar.fbx",
            "format": "fbx",
            "rigged": True,
            "rigging_evidence": [
                {"source": "https://example.test/docs", "note": "humanoid skeleton"}
            ],
        },
        policy(),
        loader=FakeLoader(blob),
    )
    assert evidenced["validAvatar"] is True
    assert evidenced["status"] == "valid_rigged_fbx"

    unevidenced = probe_asset(
        {
            "url": "https://cdn.test/avatar.fbx",
            "format": "fbx",
            "rigged": True,
            "rigging_evidence": [],
        },
        policy(),
        loader=FakeLoader(blob),
    )
    assert unevidenced["validAvatar"] is False
    assert unevidenced["status"] == "valid_fbx_rigging_unproven"


def test_collection_can_be_structurally_complete_with_mixed_supported_formats():
    collection = {
        "collection_id": "demo",
        "name": "Demo",
        "complete": True,
        "assets": [
            {"url": "https://cdn.test/1.vrm", "format": "vrm"},
            {"url": "https://cdn.test/2.glb", "format": "glb"},
            {
                "url": "https://cdn.test/3.fbx",
                "format": "fbx",
                "rigged": True,
                "rigging_evidence": [{"source": "docs"}],
            },
        ],
    }
    probes = {
        "https://cdn.test/1.vrm": {"validAvatar": True, "actualFormat": "vrm"},
        "https://cdn.test/2.glb": {"validAvatar": True, "actualFormat": "glb"},
        "https://cdn.test/3.fbx": {"validAvatar": True, "actualFormat": "fbx"},
    }
    result = collection_probe_summary(collection, probes)
    assert result["avatarReadyComplete"] is True
    assert result["validVrmUrls"] == 1
    assert result["validRiggedGlbUrls"] == 1
    assert result["validRiggedFbxUrls"] == 1
