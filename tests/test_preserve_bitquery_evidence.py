import json

from scripts.preserve_bitquery_evidence import (
    fresh_usable,
    last_good,
    main,
    placeholder_report,
    select_report,
    summary_of,
)


def report(observed: int, inspected: int = 62, errors: int = 0) -> dict:
    return {
        "summary": {
            "collectionsInspected": inspected,
            "collectionsObservedOnchain": observed,
            "collectionsWithErrors": errors,
        },
        "collections": [{"catalogId": "demo", "contractObservedOnchain": observed > 0}],
    }


def test_fresh_observations_win():
    selected, mode = select_report(report(10, errors=42), report(8))
    assert mode == "fresh"
    assert selected["summary"]["collectionsObservedOnchain"] == 10


def test_zero_fresh_observations_restore_last_good():
    selected, mode = select_report(report(0, errors=62), report(10, errors=42))
    assert mode == "previous_last_good"
    assert selected["summary"]["collectionsObservedOnchain"] == 10


def test_total_outage_without_last_good_is_unavailable():
    selected, mode = select_report(report(0, errors=62), report(0, errors=62))
    assert mode == "unavailable"
    assert selected["availability"] == "unavailable"
    assert selected["summary"]["collectionsObservedOnchain"] == 0


def test_missing_fresh_still_restores_previous():
    selected, mode = select_report(None, report(10))
    assert mode == "previous_last_good"
    assert last_good(selected)
    assert not fresh_usable(None)


def test_corrupt_and_nondict_json_fallback_and_isolated_placeholders(tmp_path):
    first = placeholder_report()
    first["summary"]["collectionsObservedOnchain"] = 99
    first["collections"].append({"catalogId": "mutated"})
    second = placeholder_report()
    assert second["summary"]["collectionsObservedOnchain"] == 0
    assert second["collections"] == []
    assert summary_of(["not", "a", "dict"]) == {}

    fresh = tmp_path / "fresh.json"
    prev = tmp_path / "prev.json"
    out = tmp_path / "out.json"
    health = tmp_path / "health.json"
    fresh.write_text("{truncated json", encoding="utf-8")
    prev.write_text(json.dumps(report(7)), encoding="utf-8")
    health.write_text("corrupt", encoding="utf-8")

    rc = main(["--fresh", str(fresh), "--previous", str(prev), "--output", str(out), "--health", str(health)])
    assert rc == 0
    selected = json.loads(out.read_text(encoding="utf-8"))
    assert selected["summary"]["collectionsObservedOnchain"] == 7
    health_doc = json.loads(health.read_text(encoding="utf-8"))
    assert health_doc["bitquery"]["mode"] == "previous_last_good"
    assert health_doc["bitquery"]["selectedObservations"] == 7
