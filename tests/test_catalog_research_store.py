import json
from pathlib import Path

import pytest

from scripts.build_catalog_research_store import run
from scripts.catalog_research_store import load_catalog_research


def test_base_and_shards_merge_by_collection(tmp_path: Path):
    base = tmp_path / "catalog_research.json"
    shards = tmp_path / "catalog_research.d"
    shards.mkdir()
    base.write_text(
        json.dumps(
            {
                "schema": "vrm-catalog-research-v1",
                "collections": {
                    "alpha": {"project_status": {"value": "active"}}
                },
            }
        ),
        encoding="utf-8",
    )
    (shards / "beta.json").write_text(
        json.dumps(
            {
                "id": "beta",
                "discord": {
                    "value": "https://discord.gg/beta",
                    "evidence": [{"source": "official"}],
                },
            }
        ),
        encoding="utf-8",
    )
    (shards / "alpha-extra.json").write_text(
        json.dumps(
            {
                "id": "alpha",
                "x": {
                    "value": "https://x.com/alpha",
                    "evidence": [{"source": "official"}],
                },
            }
        ),
        encoding="utf-8",
    )

    merged = load_catalog_research(base, shards)

    assert set(merged["collections"]) == {"alpha", "beta"}
    assert merged["collections"]["alpha"]["project_status"]["value"] == "active"
    assert merged["collections"]["alpha"]["x"]["value"] == "https://x.com/alpha"
    assert merged["collections"]["beta"]["discord"]["value"] == "https://discord.gg/beta"


def test_conflicting_duplicate_field_fails_closed(tmp_path: Path):
    base = tmp_path / "catalog_research.json"
    shards = tmp_path / "catalog_research.d"
    shards.mkdir()
    base.write_text(
        json.dumps({"collections": {"alpha": {"project_status": {"value": "active"}}}}),
        encoding="utf-8",
    )
    (shards / "alpha.json").write_text(
        json.dumps({"id": "alpha", "project_status": {"value": "sunset"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="conflicting catalog research"):
        load_catalog_research(base, shards)


def test_compiler_writes_deterministic_sorted_aggregate(tmp_path: Path):
    base = tmp_path / "base.json"
    shards = tmp_path / "shards"
    shards.mkdir()
    base.write_text(json.dumps({"collections": {"zeta": {"notes": "z"}}}), encoding="utf-8")
    (shards / "alpha.json").write_text(json.dumps({"id": "alpha", "notes": "a"}), encoding="utf-8")
    output = tmp_path / "merged.json"

    payload = run(base, shards, output, overlays=[])
    saved = json.loads(output.read_text())

    assert list(payload["collections"]) == ["alpha", "zeta"]
    assert list(saved["collections"]) == ["alpha", "zeta"]


def test_generated_overlay_fills_missing_nested_fields_but_never_overwrites_curator_data(tmp_path: Path):
    base = tmp_path / "base.json"
    shards = tmp_path / "shards"
    shards.mkdir()
    base.write_text(
        json.dumps(
            {
                "collections": {
                    "alpha": {
                        "identity": {"name": "Alpha"},
                        "discord": {
                            "value": "https://discord.gg/curated",
                            "evidence": [{"source": "curator"}],
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    overlay = tmp_path / "openpage.json"
    overlay.write_text(
        json.dumps(
            {
                "collections": {
                    "alpha": {
                        "identity": {"project_url": "https://alpha.test"},
                        "discord": {
                            "value": "https://discord.gg/provider",
                            "evidence": [{"source": "openpage"}],
                        },
                        "logo": {
                            "value": "https://alpha.test/logo.png",
                            "evidence": [{"source": "openpage"}],
                        },
                    },
                    "unknown": {"logo": {"value": "https://unknown.test/logo.png"}},
                }
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "merged.json"

    payload = run(base, shards, output, overlays=[overlay])
    alpha = payload["collections"]["alpha"]
    assert alpha["identity"] == {
        "name": "Alpha",
        "project_url": "https://alpha.test",
    }
    assert alpha["discord"]["value"] == "https://discord.gg/curated"
    assert alpha["logo"]["value"] == "https://alpha.test/logo.png"
    result = payload["overlays"][0]
    assert "alpha.identity.project_url" in result["fieldsFilled"]
    assert "alpha.logo" in result["fieldsFilled"]
    assert "alpha.discord.value" in result["curatorFieldsPreserved"]
    assert result["unknownCollections"] == ["unknown"]
