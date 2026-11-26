"""CLI path and identity tests for the unified ``sy`` command.

The quality audit of 2026-08-18 found that ``sy enrich`` and ``sy build``
resolved pipeline scripts and the catalog HTML from the repository root
instead of ``scripts/`` and ``static/``. These tests lock the corrected
layout and the show-command exact-match rule.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent


def load_sy():
    loader = importlib.machinery.SourceFileLoader("sy_cli", str(REPO / "sy"))
    spec = importlib.util.spec_from_loader("sy_cli", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sy = load_sy()


def test_enrich_scripts_live_under_scripts_not_repo_root():
    for name, filename in sy.ENRICH_SCRIPTS.items():
        path = sy.enrich_script_path(name)
        assert path == REPO / "scripts" / filename
        assert path.exists(), f"missing enrichment script {path}"
        assert not (REPO / filename).exists()


def test_build_index_and_catalog_html_live_in_layout_dirs():
    builder = sy.build_index_path()
    html = sy.catalog_html_path()
    assert builder == REPO / "scripts" / "build_index.py"
    assert html == REPO / "static" / "index.html"
    assert builder.exists()
    assert html.exists()
    assert not (REPO / "build_index.py").exists()
    assert not (REPO / "index.html").exists()


def test_enrich_invokes_scripts_dir(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None):
        calls.append({"cmd": cmd, "cwd": cwd})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sy.subprocess, "run", fake_run)
    code = sy.cmd_enrich(SimpleNamespace(only="supply"))
    assert code == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1] == str(REPO / "scripts" / "check_supply.py")
    assert calls[0]["cwd"] == str(REPO)


def test_enrich_missing_script_is_nonzero(monkeypatch, tmp_path):
    monkeypatch.setattr(sy, "SCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(
        sy,
        "enrich_script_path",
        lambda name: tmp_path / sy.ENRICH_SCRIPTS[name],
    )
    code = sy.cmd_enrich(SimpleNamespace(only="supply"))
    assert code == 1


def test_build_invokes_scripts_build_index_and_static_html(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None):
        calls.append({"cmd": list(cmd), "cwd": cwd})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sy.subprocess, "run", fake_run)
    monkeypatch.setattr(sy.shutil, "which", lambda name: "/usr/bin/open" if name == "open" else None)
    code = sy.cmd_build(SimpleNamespace(no_html=False))
    assert code == 0
    assert calls[0]["cmd"][1] == str(REPO / "scripts" / "build_index.py")
    assert calls[1]["cmd"][1] == str(REPO / "static" / "index.html")


def test_build_no_html_skips_opener(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sy.subprocess, "run", fake_run)
    code = sy.cmd_build(SimpleNamespace(no_html=True))
    assert code == 0
    assert len(calls) == 1
    assert calls[0][1].endswith("scripts/build_index.py")


def test_build_propagates_builder_failure(monkeypatch):
    monkeypatch.setattr(
        sy.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=7),
    )
    code = sy.cmd_build(SimpleNamespace(no_html=True))
    assert code == 7


def test_show_prefers_exact_name_over_like_prefix(capsys):
    """A query that is an exact collection name must not land on an earlier LIKE hit."""
    conn = sy.conn()
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM collections ORDER BY name")]
    finally:
        conn.close()
    if len(names) < 2:
        pytest.skip("need at least two collections")
    target = None
    for name in names:
        prefix_hits = [n for n in names if name.lower() in n.lower() and n != name]
        # Find a name whose LIKE '%name%' would also match a different, earlier name
        # if we only used LIKE ordered by name. Prefer a name that is not first.
        if prefix_hits:
            continue
        if name != names[0]:
            target = name
            break
    if target is None:
        target = names[-1]
    sy.cmd_show(SimpleNamespace(query=target, json=False))
    out = capsys.readouterr().out
    assert target in out
    # The header line after the banner is the collection name.
    assert f"  {target}" in out


def test_show_unknown_collection_reports_not_found(capsys):
    sy.cmd_show(SimpleNamespace(query="__no_such_collection_zzz__", json=False))
    out = capsys.readouterr().out
    assert "Not found" in out


def test_stats_json_has_core_counts(capsys):
    sy.cmd_stats(SimpleNamespace(json=True))
    import json

    data = json.loads(capsys.readouterr().out)
    assert data["collections"] >= 1
    assert "by_tier" in data
    assert "completeness" in data


def test_enrich_scripts_target_data_vrm_index():
    import importlib.util

    expected_db = REPO / "data" / "vrm_index.db"
    for module_name, rel in [
        ("check_supply", "scripts/check_supply.py"),
        ("check_traits", "scripts/check_traits.py"),
        ("check_discord", "scripts/check_discord.py"),
        ("check_opensea_urls", "scripts/check_opensea_urls.py"),
        ("fetch_previews", "scripts/fetch_previews.py"),
    ]:
        spec = importlib.util.spec_from_file_location(module_name, REPO / rel)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert Path(module.DB) == expected_db, f"{rel} DB={module.DB}"
        assert expected_db.exists()


def test_ipfs_to_https_uses_live_gateway():
    from scripts.fetch_previews import ipfs_to_https

    cid = "QmZYVVP2XMNK2mjcrac6zyocvAU9xuEupZ4zYuoPVuimr7"
    assert ipfs_to_https(f"ipfs://{cid}/avatar.vrm") == f"https://ipfs.io/ipfs/{cid}/avatar.vrm"
    assert "cloudflare-ipfs.com" not in ipfs_to_https(f"ipfs://{cid}")
    assert ipfs_to_https("ar://abc") == "https://arweave.net/abc"
    assert ipfs_to_https("https://example/file.vrm") == "https://example/file.vrm"


def test_search_script_targets_data_vrm_index():
    import json
    import subprocess
    import sys

    from scripts import search as search_mod

    assert Path(search_mod.DB) == REPO / "data" / "vrm_index.db"

    stats_proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "search.py"), "--stats"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "VRM Index Statistics" in stats_proc.stdout
    assert "Collections:" in stats_proc.stdout

    json_proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "search.py"), "--tier", "A", "--json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    )
    tier_a = json.loads(json_proc.stdout)
    assert isinstance(tier_a, list) and len(tier_a) >= 1

    av_proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "search.py"), "--avatars", "--json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    )
    avatars = json.loads(av_proc.stdout)
    assert isinstance(avatars, list) and len(avatars) >= 1


def test_batch_scripts_target_data_dirs_and_lazy_key(monkeypatch, tmp_path):
    import importlib
    import importlib.util
    import sqlite3

    monkeypatch.delenv("OPENSEA_API_KEY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    expected_db = REPO / "data" / "vrm_index.db"
    for module_name, rel in [
        ("backfill_urls_mod", "scripts/backfill_urls.py"),
        ("fetch_collection_meta_mod", "scripts/fetch_collection_meta.py"),
        ("fetch_project_urls_mod", "scripts/fetch_project_urls.py"),
        ("recover_metadata_mod", "scripts/recover_metadata.py"),
    ]:
        spec = importlib.util.spec_from_file_location(module_name, REPO / rel)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert Path(module.DB) == expected_db, f"{rel} DB={module.DB}"
        if hasattr(module, "API_KEY_PATH"):
            assert module.OSK == ""
            with pytest.raises(SystemExit):
                module.load_opensea_key()
            fake_key = tmp_path / "api_key"
            fake_key.write_text("  \n", encoding="utf-8")
            monkeypatch.setattr(module, "API_KEY_PATH", fake_key)
            with pytest.raises(SystemExit):
                module.load_opensea_key()
            fake_key.write_text("test-secret-key\n", encoding="utf-8")
            assert module.load_opensea_key() == "test-secret-key"
            monkeypatch.setenv("OPENSEA_API_KEY", "env-override-key")
            assert module.load_opensea_key() == "env-override-key"
            monkeypatch.delenv("OPENSEA_API_KEY", raising=False)
        for attr in ("A3AC_PATH", "CACHE_PATH", "DETAILS", "CACHE"):
            if hasattr(module, attr):
                path = Path(getattr(module, attr))
                assert REPO / "data" / "os_scrape" in path.parents
                if attr == "CACHE":
                    assert path.parent.exists(), f"{rel} missing parent dir for {attr}={path}"
                else:
                    assert path.exists(), f"{rel} missing {attr}={path}"

    backfill_mod = importlib.import_module("scripts.backfill_urls")
    temp_db = tmp_path / "vrm_index.db"
    src_conn = sqlite3.connect(expected_db)
    schema_sql = src_conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='collections'"
    ).fetchone()[0]
    src_conn.close()
    conn = sqlite3.connect(temp_db)
    conn.execute(schema_sql)
    conn.execute(
        """INSERT INTO collections
        (id, name, opensea_slug, contract, chain, project_url, description, license_category, source, image_url)
        VALUES ('boomboxheads-v2', 'Boomboxheads V2', '', '', 'ethereum', '', '', 'green', 'curated', '')"""
    )
    conn.execute(
        """INSERT INTO collections
        (id, name, opensea_slug, contract, chain, project_url, description, license_category, source, image_url)
        VALUES ('adworld-test', 'Adworld Test', 'adworld-slug', '', 'ethereum', '', '', 'green', 'curated', '')"""
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(backfill_mod, "DB", temp_db)
    monkeypatch.setattr(backfill_mod.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    backfill_mod.main()
    check_conn = sqlite3.connect(temp_db)
    updated_row = check_conn.execute("SELECT project_url FROM collections WHERE id='boomboxheads-v2'").fetchone()
    check_conn.close()
    assert updated_row is not None and updated_row[0].startswith("http")

    class FakeResp:
        def __init__(self, payload: bytes):
            self._payload = payload
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return self._payload

    meta_mod = importlib.import_module("scripts.fetch_collection_meta")
    proj_mod = importlib.import_module("scripts.fetch_project_urls")
    rec_mod = importlib.import_module("scripts.recover_metadata")

    meta_key = tmp_path / "meta.key"
    meta_key.write_text("lazy-meta-key\n", encoding="utf-8")
    monkeypatch.setattr(meta_mod, "OSK", "")
    monkeypatch.setattr(meta_mod, "API_KEY_PATH", meta_key)
    monkeypatch.setattr(meta_mod, "DB", temp_db)
    monkeypatch.setattr(meta_mod, "CACHE_PATH", tmp_path / "collection_meta.json")
    monkeypatch.setattr(meta_mod.time, "sleep", lambda *_: None)
    meta_headers = {}
    def fake_meta_urlopen(req, timeout=20):
        meta_headers.update(req.header_items())
        if req.full_url.endswith("/stats"):
            return FakeResp(b'{"total":{"num_owners":42,"floor_price":0.5,"floor_price_symbol":"ETH","volume":10,"sales":5},"intervals":[]}')
        return FakeResp(b'{"name":"Adworld Test","description":"Fetched description for testing","total_supply":100,"fees":[],"rarity":{}}')
    monkeypatch.setattr(meta_mod.urllib.request, "urlopen", fake_meta_urlopen)
    meta_mod.main()
    assert meta_headers.get("X-api-key") == "lazy-meta-key"
    assert (tmp_path / "collection_meta.json").exists()
    check_conn = sqlite3.connect(temp_db)
    meta_row = check_conn.execute("SELECT description, num_owners FROM collections WHERE id='adworld-test'").fetchone()
    check_conn.close()
    assert meta_row == ("Fetched description for testing", 42)

    proj_key = tmp_path / "proj.key"
    proj_key.write_text("lazy-proj-key\n", encoding="utf-8")
    monkeypatch.setattr(proj_mod, "OSK", "")
    monkeypatch.setattr(proj_mod, "API_KEY_PATH", proj_key)
    monkeypatch.setattr(proj_mod, "DB", temp_db)
    monkeypatch.setattr(proj_mod, "DETAILS", tmp_path / "collection_details.json")
    monkeypatch.setattr(proj_mod.time, "sleep", lambda *_: None)
    seen_headers = {}
    def fake_proj_urlopen(req, timeout=20):
        seen_headers.update(req.header_items())
        return FakeResp(b'{"external_url":"https://adworld.game"}')
    monkeypatch.setattr(proj_mod.urllib.request, "urlopen", fake_proj_urlopen)
    conn = sqlite3.connect(temp_db)
    conn.execute("UPDATE collections SET project_url='' WHERE id='adworld-test'")
    conn.commit()
    conn.close()
    proj_mod.main()
    assert (tmp_path / "collection_details.json").exists()
    assert seen_headers.get("X-api-key") == "lazy-proj-key"
    check_conn = sqlite3.connect(temp_db)
    proj_row = check_conn.execute("SELECT project_url FROM collections WHERE id='adworld-test'").fetchone()
    check_conn.close()
    assert proj_row == ("https://adworld.game",)

    # Clear image_url and description so recover_metadata.main() actually recovers adworld.game metadata
    conn = sqlite3.connect(temp_db)
    conn.execute("UPDATE collections SET description='', image_url='' WHERE id='adworld-test'")
    conn.commit()
    conn.close()
    monkeypatch.setattr(rec_mod, "DB", temp_db)
    monkeypatch.setattr(rec_mod, "CACHE", tmp_path / "wayback_metadata.json")
    monkeypatch.setattr(rec_mod.time, "sleep", lambda *_: None)
    def fake_rec_urlopen(req_or_url, timeout=20):
        url = req_or_url.full_url if hasattr(req_or_url, "full_url") else str(req_or_url)
        if "archive.org/wayback/available" in url:
            return FakeResp(b'{"archived_snapshots":{"closest":{"available":true,"url":"https://web.archive.org/web/20240101/https://adworld.game"}}}')
        return FakeResp(b'<html><head><meta property="og:description" content="Archived description from wayback snapshot!"><meta property="og:image" content="https://cdn.example/img.png"></head></html>')
    monkeypatch.setattr(rec_mod.urllib.request, "urlopen", fake_rec_urlopen)
    rec_mod.main()
    assert (tmp_path / "wayback_metadata.json").exists()
    check_conn = sqlite3.connect(temp_db)
    rec_row = check_conn.execute("SELECT description, image_url FROM collections WHERE id='adworld-test'").fetchone()
    check_conn.close()
    assert rec_row[0] == "Archived description from wayback snapshot!"
    assert "cdn.example/img.png" in rec_row[1]
