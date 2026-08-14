import json
from pathlib import Path

from scripts.build_catalog_research_queue import run


def test_queue_prioritizes_inventory_and_maps_sources(tmp_path: Path):
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps(
            {
                "schema": "avatar-catalog-acceptance-v1",
                "failures": [
                    {
                        "id": "social-gap",
                        "name": "Social Gap",
                        "reasons": [
                            "discord:actual_value_required",
                            "x:actual_value_required",
                        ],
                    },
                    {
                        "id": "inventory-gap",
                        "name": "Inventory Gap",
                        "reasons": [
                            "avatar_inventory:explicit_exhaustive_assets_required",
                            "file_access:explicit_access_mode_required",
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "queue.json"

    payload = run(acceptance, output)

    assert payload["summary"]["collections"] == 2
    assert payload["summary"]["fieldCounts"]["avatar_inventory"] == 1
    assert payload["summary"]["fieldCounts"]["discord"] == 1
    assert payload["queue"][0]["id"] == "inventory-gap"
    assert payload["queue"][0]["priority"] == 100
    assert "OpenPage avatar records and MML model references" in payload["queue"][0]["researchPlan"]["avatar_inventory"]
    assert "official site/community page" in payload["queue"][1]["researchPlan"]["discord"]
    assert json.loads(output.read_text())["schema"] == "avatar-catalog-research-queue-v2"


def test_legacy_vrm_inventory_reasons_still_route():
    # The VRM-specific discovery pipeline remains supported as a research lane.
    assert "Moralis cursor-exhausted collection NFTs" in __import__(
        "scripts.build_catalog_research_queue", fromlist=["SOURCE_PLAN"]
    ).SOURCE_PLAN["vrm_inventory"]


def test_queue_uses_reason_prefix_as_field(tmp_path: Path):
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps(
            {
                "failures": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "reasons": ["launch_date:actual_value_required"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "queue.json"

    payload = run(acceptance, output)

    assert payload["queue"][0]["missingFields"] == ["launch_date"]
    assert "contemporaneous mint/drop announcement" in payload["queue"][0]["researchPlan"]["launch_date"]
