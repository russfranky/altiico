import json
import urllib.error
from types import SimpleNamespace

import pytest

from scripts import discover_blockscout_vrms


def test_blockscout_http_403_returns_unavailable_report(tmp_path, monkeypatch):
    def fake_get_json(url, timeout):
        raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(discover_blockscout_vrms, "_get_json", fake_get_json)
    out = tmp_path / "robinhood_report.json"

    rc = discover_blockscout_vrms.main(
        [
            "--chain",
            "robinhood",
            "--output",
            str(out),
            "--max-contracts",
            "10",
            "--max-pages",
            "1",
        ]
    )

    assert rc == 0
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["availability"] == "unavailable"
    assert report["summary"]["availability"] == "unavailable"
    assert report["summary"]["nft_contracts_discovered"] == 0
    assert report["contracts"] == []
    assert "403" in report["source_error"]


def test_blockscout_partial_pagination_error_preserves_first_page(tmp_path, monkeypatch):
    calls = []

    def fake_get_json(url, timeout):
        calls.append(url)
        if "/instances" in url:
            return {"items": []}
        if len(calls) == 1:
            return {
                "items": [
                    {
                        "address": "0x1111111111111111111111111111111111111111",
                        "name": "Sample",
                        "symbol": "SMP",
                        "type": "ERC-721",
                        "total_supply": "1",
                    }
                ],
                "next_page_params": {"cursor": "2"},
            }
        raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(discover_blockscout_vrms, "_get_json", fake_get_json)
    out = tmp_path / "robinhood_partial.json"

    rc = discover_blockscout_vrms.main(
        [
            "--chain",
            "robinhood",
            "--output",
            str(out),
            "--max-contracts",
            "10",
            "--max-pages",
            "2",
        ]
    )

    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["availability"] == "partial"
    assert report["summary"]["availability"] == "partial"
    assert report["summary"]["blockscout_pages"] == 1
    assert report["summary"]["nft_contracts_discovered"] == 1
    assert len(report["contracts"]) == 1
    assert "403" in report["source_error"]


def test_blockscout_unconfigured_chain_still_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(
        discover_blockscout_vrms,
        "get_chain",
        lambda key: SimpleNamespace(key=key, blockscout_api=None),
    )

    with pytest.raises(SystemExit):
        discover_blockscout_vrms.main(
            [
                "--chain",
                "custom-no-blockscout",
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
