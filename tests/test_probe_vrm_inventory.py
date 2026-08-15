import json
import struct
from types import SimpleNamespace

from scripts.crawler.fetch import GLB_MAGIC, GLB_VERSION_2, JSON_CHUNK_TYPE
from scripts.crawler.models import CrawlPolicy
from scripts.probe_vrm_inventory import collection_probe_summary, probe_url


def policy():
    return CrawlPolicy(
        max_depth=0,
        request_budget=100,
        max_tasks=100,
        max_attempts=1,
        timeout=1,
        max_document_bytes=1024,
        max_vrm_json_bytes=1024 * 1024,
        max_vrm_bytes=8 * 1024 * 1024,
        max_links_per_document=0,
    )


def glb_json(extensions):
    payload = json.dumps({"asset": {"version": "2.0"}, "extensions": extensions}).encode()
    while len(payload) % 4:
        payload += b" "
    total = 20 + len(payload)
    header = struct.pack("<III", GLB_MAGIC, GLB_VERSION_2, total)
    chunk = struct.pack("<II", len(payload), JSON_CHUNK_TYPE)
    return header + chunk + payload


class FakeLoader:
    def __init__(self, blob):
        self.blob = blob

    def fetch_range(self, url, start, end, *, preferred_transport=None):
        return SimpleNamespace(
            body=self.blob[start : end + 1],
            network_requests=1,
            final_url="https://transport.test/avatar.vrm",
        )


def test_probe_accepts_vrm1_from_header_and_json_chunk_only():
    blob = glb_json({"VRMC_vrm": {"specVersion": "1.0", "meta": {}}})
    result = probe_url("https://cdn.test/avatar.vrm", policy(), loader=FakeLoader(blob))
    assert result["validVrm"] is True
    assert result["status"] == "valid_vrm"
    assert result["vrmSpec"] == "1.0"
    assert result["networkRequests"] == 2


def test_probe_rejects_plain_glb():
    blob = glb_json({"KHR_materials_unlit": {}})
    result = probe_url("https://cdn.test/avatar.vrm", policy(), loader=FakeLoader(blob))
    assert result["validVrm"] is False
    assert result["status"] == "valid_glb_not_vrm"


def test_collection_requires_every_inventory_url_to_probe_valid():
    collection = {
        "catalogId": "demo",
        "name": "Demo",
        "metadataComplete": True,
        "vrmUrls": ["https://cdn.test/1.vrm", "https://cdn.test/2.vrm"],
    }
    probes = {
        "https://cdn.test/1.vrm": {"validVrm": True},
        "https://cdn.test/2.vrm": {"validVrm": False},
    }
    result = collection_probe_summary(collection, probes)
    assert result["structurallyComplete"] is False
    assert result["invalidUrls"] == ["https://cdn.test/2.vrm"]


def test_evidenced_terminal_collection_needs_no_fake_urls():
    collection = {
        "catalogId": "sunset",
        "name": "Sunset",
        "terminalResearchState": "unrecoverable",
        "metadataComplete": True,
        "vrmUrls": [],
    }
    result = collection_probe_summary(collection, {})
    assert result["structurallyComplete"] is True
    assert result["urls"] == 0
