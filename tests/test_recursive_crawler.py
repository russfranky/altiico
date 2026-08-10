"""Offline tests for the persistent recursive catalog crawler."""

from __future__ import annotations

import base64
import json
import socket
import sqlite3
import struct
from pathlib import Path

import pytest

from scripts.crawler.engine import RecursiveCrawler
from scripts.crawler.fetch import EvmTokenResolver, NetworkLoader
from scripts.crawler.models import (
    Binding,
    CrawlPolicy,
    FetchResult,
    PermanentCrawlError,
    VrmValidation,
)
from scripts.crawler.store import CrawlStore
from scripts.crawler.uri import (
    canonicalize_uri,
    decode_data_json,
    discover_links,
    resolve_uri,
    transport_candidates,
)


def make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE collections (
            id TEXT PRIMARY KEY,
            sample_metadata_url TEXT,
            vrm_url_https TEXT,
            vrm_url_pattern TEXT,
            vrm_reachable INTEGER,
            vrm_check_status TEXT,
            vrm_check_bytes INTEGER,
            vrm_check_url TEXT,
            vrm_checked_at TEXT
        );
        CREATE TABLE avatars (
            id TEXT PRIMARY KEY,
            collection_id TEXT,
            model_file_url TEXT,
            reachable INTEGER,
            check_status TEXT,
            checked_at TEXT
        );
        CREATE TABLE vrm_metadata (
            source_url TEXT PRIMARY KEY,
            source_etag TEXT,
            source_last_modified TEXT,
            extracted_at TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            vrm_spec TEXT,
            vrm_meta_json TEXT,
            parse_error TEXT,
            content_length INTEGER,
            content_range TEXT
        );
        CREATE TABLE avatar_vrm (
            avatar_id TEXT PRIMARY KEY,
            vrm_source_url TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


class FakeLoader:
    def __init__(self, documents=None, validations=None):
        self.documents = {
            canonicalize_uri(key): value for key, value in (documents or {}).items()
        }
        self.validations = {
            canonicalize_uri(key): value for key, value in (validations or {}).items()
        }
        self.json_calls: list[str] = []
        self.asset_calls: list[str] = []

    def load_json(self, url: str):
        canonical = canonicalize_uri(url)
        self.json_calls.append(canonical)
        document = self.documents[canonical]
        body = json.dumps(document).encode()
        return (
            document,
            FetchResult(
                canonical_url=canonical,
                final_url=transport_candidates(canonical)[0],
                status="ok",
                http_status=200,
                content_type="application/json",
                body=body,
                network_requests=1,
            ),
            "f" * 64,
        )

    def validate_vrm(self, url: str):
        canonical = canonicalize_uri(url)
        self.asset_calls.append(canonical)
        return self.validations[canonical]


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "catalog.db"
    make_db(db)
    with CrawlStore(db) as value:
        value.ensure_schema()
        yield value


def valid(url: str, *, transport: str | None = None) -> VrmValidation:
    canonical = canonicalize_uri(url)
    return VrmValidation(
        canonical_url=canonical,
        transport_url=transport or transport_candidates(canonical)[0],
        valid=True,
        status="valid_vrm",
        vrm_spec="1.0",
        raw_meta={"name": "Recursive Test"},
        total_length=1234,
        content_sha256="a" * 64,
        network_requests=2,
    )


def rejected(url: str) -> VrmValidation:
    canonical = canonicalize_uri(url)
    return VrmValidation(
        canonical_url=canonical,
        transport_url=transport_candidates(canonical)[0],
        valid=False,
        status="valid_glb_not_vrm",
        vrm_spec=None,
        raw_meta=None,
        total_length=987,
        content_sha256="b" * 64,
        network_requests=2,
        error="no VRM extension",
    )


# ---------------------------------------------------------------- URI logic


def test_canonicalize_gateway_to_ipfs_preserves_case():
    assert canonicalize_uri(
        "https://ipfs.io/ipfs/BaSe58CID/Avatar.vrm#viewer"
    ) == "ipfs://BaSe58CID/Avatar.vrm"


def test_common_ipfs_double_prefix_is_normalized():
    assert canonicalize_uri("ipfs://ipfs/BaSe58CID/path.json") == \
        "ipfs://BaSe58CID/path.json"


def test_ipfs_transport_candidates_do_not_change_cid_case():
    assert transport_candidates("ipfs://BaSe58CID/Avatar.vrm") == [
        "https://ipfs.io/ipfs/BaSe58CID/Avatar.vrm",
        "https://dweb.link/ipfs/BaSe58CID/Avatar.vrm",
    ]


def test_relative_ipfs_links_resolve_hierarchically():
    assert resolve_uri(
        "ipfs://CID/metadata/42.json", "../models/42.vrm"
    ) == "ipfs://CID/models/42.vrm"


def test_json_data_uri_supports_percent_and_base64():
    raw = b'{"vrm_url":"ipfs://CID/a.vrm"}'
    percent = "data:application/json," + __import__("urllib.parse").parse.quote_from_bytes(raw)
    encoded = "data:application/json;base64," + base64.b64encode(raw).decode()
    assert decode_data_json(percent, 1_000) == raw
    assert decode_data_json(encoded, 1_000) == raw


def test_recursive_link_discovery_parses_embedded_json_and_ignores_web_links():
    document = {
        "external_url": "https://project.example/",
        "metadata_url": "./nested/next.json",
        "payload": json.dumps(
            {
                "properties": {
                    "files": [
                        {"uri": "ipfs://CID/Avatar.vrm", "type": "model/vrm"}
                    ]
                }
            }
        ),
    }
    links = discover_links(document, "https://metadata.example/root/1.json")
    by_kind = {(link.kind, link.url): link for link in links}
    assert ("metadata", "https://metadata.example/root/nested/next.json") in by_kind
    assert ("asset", "ipfs://CID/Avatar.vrm") in by_kind
    assert all(link.url != "https://project.example/" for link in links)


def test_gltf_binary_is_candidate_not_proof():
    links = discover_links(
        {"files": [{"uri": "https://cdn.example/model.glb", "type": "model/gltf-binary"}]},
        "https://cdn.example/meta.json",
    )
    assert len(links) == 1
    assert links[0].kind == "asset"
    assert links[0].confidence < 0.9


# ----------------------------------------------------------- store/frontier


def test_frontier_deduplicates_fetch_but_keeps_multiple_bindings(store):
    policy = CrawlPolicy(request_budget=10)
    run_id = store.create_run(policy)
    first = store.enqueue(
        run_id,
        kind="asset",
        canonical_key="ipfs://CID/a.vrm",
        payload={"url": "ipfs://CID/a.vrm"},
        depth=0,
        bindings=[Binding("collection-a", "", "one")],
    )
    second = store.enqueue(
        run_id,
        kind="asset",
        canonical_key="ipfs://CID/a.vrm",
        payload={"url": "ipfs://CID/a.vrm"},
        depth=1,
        bindings=[Binding("collection-b", "", "two")],
    )
    assert first == second
    assert store.task_count(run_id) == 1
    assert {b.collection_id for b in store.bindings_for_task(first)} == {
        "collection-a",
        "collection-b",
    }


def test_expired_lease_is_resumable(store):
    run_id = store.create_run(CrawlPolicy())
    task_id = store.enqueue(
        run_id,
        kind="metadata",
        canonical_key="https://example.com/a.json",
        payload={"url": "https://example.com/a.json"},
        depth=0,
    )
    claimed = store.claim_next(run_id, lease_seconds=300)
    assert claimed and claimed.id == task_id
    store.conn.execute(
        "UPDATE crawl_tasks SET lease_until='2000-01-01T00:00:00Z' WHERE id=?",
        (task_id,),
    )
    store.conn.commit()
    assert store.recover_expired_leases(run_id) == 1
    claimed_again = store.claim_next(run_id, lease_seconds=300)
    assert claimed_again and claimed_again.attempts == 2


# --------------------------------------------------------------- crawl graph


def test_recursive_cycle_completes_each_document_once(store):
    docs = {
        "https://example.com/a.json": {"metadata_url": "b.json"},
        "https://example.com/b.json": {"metadata_url": "a.json"},
    }
    loader = FakeLoader(documents=docs)
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(request_budget=10, max_depth=5),
        loader=loader,
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    crawler.seed_metadata(run_id, "https://example.com/a.json", collection_id="c1")
    summary = crawler.run(run_id)
    assert summary.status == "completed"
    assert loader.json_calls == [
        "https://example.com/a.json",
        "https://example.com/b.json",
    ]
    assert store.task_count(run_id) == 2
    assert summary.task_counts == {"done": 2}


def test_request_budget_pauses_with_durable_pending_work(store):
    docs = {
        "https://example.com/a.json": {"metadata_url": "b.json"},
        "https://example.com/b.json": {},
    }
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(request_budget=1),
        loader=FakeLoader(documents=docs),
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    crawler.seed_metadata(run_id, "https://example.com/a.json")
    summary = crawler.run(run_id)
    assert summary.status == "budget_exhausted"
    assert summary.requests_used == 1
    assert store.pending_count(run_id) == 1


def test_depth_limit_prevents_child_enqueuing(store):
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(request_budget=10, max_depth=0),
        loader=FakeLoader(
            documents={"https://example.com/a.json": {"metadata_url": "b.json"}}
        ),
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    crawler.seed_metadata(run_id, "https://example.com/a.json")
    summary = crawler.run(run_id)
    assert summary.status == "completed"
    assert store.task_count(run_id) == 1
    assert summary.observations >= 2


def test_shared_asset_is_validated_once_and_materialized_to_each_binding(store):
    store.conn.executemany(
        "INSERT INTO collections(id) VALUES (?)", [("c1",), ("c2",)]
    )
    store.conn.commit()
    asset = "ipfs://CID/shared.vrm"
    loader = FakeLoader(validations={asset: valid(asset)})
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(request_budget=10),
        loader=loader,
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    crawler.seed_asset(run_id, asset, collection_id="c1")
    crawler.seed_asset(run_id, asset, collection_id="c2")
    summary = crawler.run(run_id)
    assert summary.status == "completed"
    assert loader.asset_calls == [asset]
    assert crawler.materialize(run_id) == 2
    rows = store.conn.execute(
        "SELECT id, vrm_check_status, vrm_url_https FROM collections ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("c1", "ok_vrm", "https://ipfs.io/ipfs/CID/shared.vrm"),
        ("c2", "ok_vrm", "https://ipfs.io/ipfs/CID/shared.vrm"),
    ]


def test_reachable_non_vrm_never_materializes(store):
    store.conn.execute("INSERT INTO collections(id) VALUES ('c1')")
    store.conn.commit()
    asset = "https://cdn.example/model.glb"
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(request_budget=10),
        loader=FakeLoader(validations={asset: rejected(asset)}),
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    crawler.seed_asset(run_id, asset, collection_id="c1")
    crawler.run(run_id)
    assert crawler.materialize(run_id) == 0
    row = store.conn.execute(
        "SELECT vrm_check_status, vrm_url_https FROM collections WHERE id='c1'"
    ).fetchone()
    assert tuple(row) == (None, None)


def test_materializer_will_not_create_unidentified_collection(store):
    asset = "ipfs://CID/new.vrm"
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(request_budget=10),
        loader=FakeLoader(validations={asset: valid(asset)}),
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    crawler.seed_asset(run_id, asset, collection_id="not-in-catalog")
    crawler.run(run_id)
    assert crawler.materialize(run_id) == 0
    assert store.conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0] == 0


def test_avatar_binding_updates_linkage_and_reachability(store):
    store.conn.execute("INSERT INTO collections(id) VALUES ('c1')")
    store.conn.execute(
        "INSERT INTO avatars(id, collection_id) VALUES ('a1', 'c1')"
    )
    store.conn.commit()
    asset = "ipfs://CID/avatar.vrm"
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(request_budget=10),
        loader=FakeLoader(validations={asset: valid(asset)}),
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    crawler.seed_asset(run_id, asset, collection_id="c1", avatar_id="a1")
    crawler.run(run_id)
    assert crawler.materialize(run_id) == 1
    avatar = store.conn.execute(
        "SELECT reachable, check_status, model_file_url FROM avatars WHERE id='a1'"
    ).fetchone()
    assert tuple(avatar) == (1, "ok_vrm", "https://ipfs.io/ipfs/CID/avatar.vrm")
    link = store.conn.execute(
        "SELECT vrm_source_url FROM avatar_vrm WHERE avatar_id='a1'"
    ).fetchone()[0]
    assert link == asset


# ---------------------------------------------------------- GLB / EVM helpers


def make_glb(extensions: dict) -> bytes:
    payload = json.dumps(
        {"asset": {"version": "2.0"}, "extensions": extensions},
        separators=(",", ":"),
    ).encode()
    padding = (-len(payload)) % 4
    payload += b" " * padding
    total = 20 + len(payload)
    return struct.pack("<IIIII", 0x46546C67, 2, total, len(payload), 0x4E4F534A) + payload


class MemoryRangeLoader:
    def __init__(self, blob: bytes, policy: CrawlPolicy | None = None):
        self.blob = blob
        self.policy = policy or CrawlPolicy()

    def fetch_range(self, canonical_url, start, end, preferred_transport=None):
        return FetchResult(
            canonical_url=canonicalize_uri(canonical_url),
            final_url="https://cdn.example/avatar.vrm",
            status="ok",
            http_status=206,
            content_type="model/vrm",
            body=self.blob[start : end + 1],
            network_requests=1,
        )


def test_partial_glb_validator_confirms_vrm_1():
    loader = MemoryRangeLoader(
        make_glb({"VRMC_vrm": {"meta": {"name": "Test", "authors": ["A"]}}})
    )
    result = NetworkLoader.validate_vrm(loader, "https://cdn.example/avatar.vrm")
    assert result.valid is True
    assert result.vrm_spec == "1.0"
    assert result.raw_meta == {"name": "Test", "authors": ["A"]}
    assert result.network_requests == 2


def test_partial_glb_validator_rejects_non_vrm_glb():
    loader = MemoryRangeLoader(make_glb({"KHR_materials_unlit": {}}))
    result = NetworkLoader.validate_vrm(loader, "https://cdn.example/model.glb")
    assert result.valid is False
    assert result.status == "valid_glb_not_vrm"


def test_evm_abi_string_decoder_and_erc1155_template():
    value = "ipfs://CID/{id}.json".encode()
    padded = value + b"\x00" * ((32 - len(value) % 32) % 32)
    encoded = "0x" + (
        (32).to_bytes(32, "big")
        + len(value).to_bytes(32, "big")
        + padded
    ).hex()
    assert EvmTokenResolver.decode_abi_string(encoded) == "ipfs://CID/{id}.json"
    expanded = EvmTokenResolver.expand_erc1155_template(
        "ipfs://CID/{id}.json", 15
    )
    assert expanded == "ipfs://CID/" + ("0" * 63) + "f.json"


def test_ssrf_guard_rejects_loopback(store):
    def loopback_resolver(host, port, type):  # noqa: A002
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    loader = NetworkLoader(store, CrawlPolicy(), resolver=loopback_resolver)
    with pytest.raises(PermanentCrawlError, match="blocked non-public"):
        loader.assert_public_url("http://metadata.internal/test.json")


# ------------------------------------------------------------- existing seeds


def test_seed_existing_skips_templates_and_can_include_avatars(store):
    store.conn.execute(
        """
        INSERT INTO collections
            (id, sample_metadata_url, vrm_url_pattern, vrm_check_status)
        VALUES ('c1', 'https://example.com/1.json',
                'https://cdn.example/{token_id}.vrm', NULL)
        """
    )
    store.conn.execute(
        "INSERT INTO avatars(id, collection_id, model_file_url) VALUES "
        "('a1', 'c1', 'https://cdn.example/a1.vrm')"
    )
    store.conn.commit()
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(),
        loader=FakeLoader(),
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    seeded = crawler.seed_existing_catalog(run_id, include_avatars=True)
    assert seeded == 2
    kinds = [
        row[0]
        for row in store.conn.execute(
            "SELECT kind FROM crawl_tasks WHERE run_id=? ORDER BY kind", (run_id,)
        )
    ]
    assert kinds == ["asset", "metadata"]


def test_materializer_preserves_different_already_confirmed_collection_url(store):
    store.conn.execute(
        """
        INSERT INTO collections(id, vrm_url_https, vrm_check_status, vrm_reachable)
        VALUES ('c1', 'https://cdn.example/original.vrm', 'ok_vrm', 1)
        """
    )
    store.conn.commit()
    asset = "ipfs://CID/new-valid.vrm"
    crawler = RecursiveCrawler(
        store,
        CrawlPolicy(request_budget=10),
        loader=FakeLoader(validations={asset: valid(asset)}),
        sleeper=lambda _: None,
    )
    run_id = crawler.new_run()
    crawler.seed_asset(run_id, asset, collection_id="c1")
    crawler.run(run_id)
    crawler.materialize(run_id)
    row = store.conn.execute(
        "SELECT vrm_url_https, vrm_check_status FROM collections WHERE id='c1'"
    ).fetchone()
    assert tuple(row) == ("https://cdn.example/original.vrm", "ok_vrm")
    assert store.conn.execute(
        "SELECT COUNT(*) FROM vrm_metadata WHERE source_url=?", (asset,)
    ).fetchone()[0] == 1


class FakeHttpResponse:
    def __init__(self, body: bytes, *, status: int = 200, headers=None):
        self._body = body
        self.status = status
        self.headers = headers or {}

    def getcode(self):
        return self.status

    def read(self, size=-1):
        return self._body if size < 0 else self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout, dict(request.headers)))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def public_resolver(host, port, type):  # noqa: A002
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]


def test_json_resource_cache_avoids_refetch_across_calls(store):
    opener = FakeOpener(
        [FakeHttpResponse(b'{"metadata_url":"next.json"}', headers={"Content-Type": "application/json"})]
    )
    loader = NetworkLoader(store, CrawlPolicy(), resolver=public_resolver, opener=opener)
    first_doc, first_result, first_hash = loader.load_json("https://example.com/a.json")
    second_doc, second_result, second_hash = loader.load_json("https://example.com/a.json")
    assert first_doc == second_doc == {"metadata_url": "next.json"}
    assert first_result.network_requests == 1
    assert second_result.network_requests == 0
    assert second_result.from_cache is True
    assert first_hash == second_hash
    assert len(opener.calls) == 1


def test_range_request_tolerates_server_ignoring_range(store):
    blob = b"0123456789" * 20
    opener = FakeOpener([FakeHttpResponse(blob, status=200)])
    loader = NetworkLoader(store, CrawlPolicy(), resolver=public_resolver, opener=opener)
    result = loader.fetch_range("https://example.com/large.vrm", 20, 39)
    assert result.body == blob[20:40]
    assert result.network_requests == 1


def test_redirect_destination_is_revalidated_for_ssrf(store):
    error = __import__("urllib.error").error.HTTPError(
        "https://example.com/start",
        302,
        "Found",
        {"Location": "http://127.0.0.1/private"},
        None,
    )
    opener = FakeOpener([error])

    def resolver(host, port, type):  # noqa: A002
        address = "127.0.0.1" if host == "127.0.0.1" else "8.8.8.8"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    loader = NetworkLoader(store, CrawlPolicy(), resolver=resolver, opener=opener)
    with pytest.raises(PermanentCrawlError) as caught:
        loader._request_transport("https://example.com/start", max_bytes=100)
    assert caught.value.error_class == "blocked_destination"
    assert caught.value.request_count == 1
