from scripts.preserve_bitquery_evidence import fresh_usable, last_good, select_report


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
