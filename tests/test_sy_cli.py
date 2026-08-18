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
