import json

from scripts.probe_dickbuttverse_inventory import (
    known_proven_ids,
    select_full_ids,
    select_probe_ids,
    url_for,
)


def test_probe_ids_are_bounded_deterministic_and_span_supply():
    first = select_probe_ids(5363, 96)
    second = select_probe_ids(5363, 96)

    assert first == second
    assert len(first) == 96
    assert len(set(first)) == 96
    assert first[0] == 0
    assert first[-1] == 5362
    assert all(0 <= token_id < 5363 for token_id in first)


def test_full_sample_prefers_ids_without_existing_binary_proof():
    structural = list(range(100))
    known = set(range(25))

    selected = select_full_ids(structural, known, 24)

    assert len(selected) == 24
    assert not (set(selected) & known)


def test_full_sample_falls_back_when_every_structural_id_is_known():
    structural = [0, 1, 2]
    selected = select_full_ids(structural, {0, 1, 2}, 2)

    assert len(selected) == 2
    assert set(selected) <= set(structural)


def test_known_proven_ids_reads_only_target_collection(tmp_path):
    path = tmp_path / "reconciliation.json"
    path.write_text(
        json.dumps(
            {
                "reconciled": [
                    {"catalogId": "dickbuttverse", "tokenId": "0"},
                    {"catalogId": "dickbuttverse", "tokenId": "1000"},
                    {"catalogId": "other", "tokenId": "7"},
                    {"catalogId": "dickbuttverse", "tokenId": "not-a-number"},
                ]
            }
        )
    )

    assert known_proven_ids(path) == {0, 1000}


def test_url_template_is_exact_and_token_scoped():
    assert url_for(4326) == (
        "https://small.deccdn.com/paths/dbvTour/3dassets/assets/sept30/vrm/4326.vrm"
    )
