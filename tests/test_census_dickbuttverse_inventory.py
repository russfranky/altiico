import json

from scripts.census_dickbuttverse_inventory import (
    compress_ranges,
    reusable_previous_rows,
    summarize,
)


def test_compress_ranges_preserves_holes():
    assert compress_ranges([0, 1, 2, 5, 7, 8]) == [
        {"start": 0, "end": 2, "count": 3},
        {"start": 5, "end": 5, "count": 1},
        {"start": 7, "end": 8, "count": 2},
    ]


def test_summary_separates_structural_vrm_404_and_retryable_errors():
    rows = [
        {"assetId": 0, "status": "structural_vrm"},
        {"assetId": 1, "status": "structural_vrm"},
        {"assetId": 2, "status": "permanent_error", "errorClass": "http_404"},
        {"assetId": 3, "status": "transport_error", "errorClass": "rate_limited"},
        {"assetId": 4, "status": "structural_vrm"},
    ]

    result = summarize(rows, 5)

    assert result["assetIdsCensused"] == 5
    assert result["structuralVrmAssets"] == 3
    assert result["structuralVrmRate"] == 0.6
    assert result["missing404Assets"] == 1
    assert result["missing404Ranges"] == [{"start": 2, "end": 2, "count": 1}]
    assert result["otherErrorAssets"] == 1
    assert result["retryableUnresolvedAssets"] == 1
    assert result["retryableUnresolvedRanges"] == [{"start": 3, "end": 3, "count": 1}]
    assert result["errorClassCounts"] == {"http_404": 1, "rate_limited": 1}


def test_resume_reuses_settled_rows_but_not_transport_failures(tmp_path):
    output = tmp_path / "census.json"
    output.write_text(
        json.dumps(
            {
                "schema": "dickbuttverse-inventory-census-v1",
                "collection": {
                    "catalogId": "dickbuttverse",
                    "catalogSupplyReference": 4,
                },
                "assets": [
                    {"assetId": 0, "status": "structural_vrm"},
                    {"assetId": 1, "status": "permanent_error", "errorClass": "http_404"},
                    {"assetId": 2, "status": "transport_error", "errorClass": "rate_limited"},
                    {"assetId": 3, "status": "probe_error", "errorClass": "ValueError"},
                ],
            }
        )
    )

    reused = reusable_previous_rows(output, 4)

    assert set(reused) == {0, 1}
    assert reused[0]["status"] == "structural_vrm"
    assert reused[1]["errorClass"] == "http_404"
