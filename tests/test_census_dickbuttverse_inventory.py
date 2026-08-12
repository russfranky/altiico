from scripts.census_dickbuttverse_inventory import compress_ranges, summarize


def test_compress_ranges_preserves_holes():
    assert compress_ranges([0, 1, 2, 5, 7, 8]) == [
        {"start": 0, "end": 2, "count": 3},
        {"start": 5, "end": 5, "count": 1},
        {"start": 7, "end": 8, "count": 2},
    ]


def test_summary_separates_structural_vrm_404_and_other_errors():
    rows = [
        {"assetId": 0, "status": "structural_vrm"},
        {"assetId": 1, "status": "structural_vrm"},
        {"assetId": 2, "status": "permanent_error", "errorClass": "http_404"},
        {"assetId": 3, "status": "transport_error", "errorClass": "timeout"},
        {"assetId": 4, "status": "structural_vrm"},
    ]

    result = summarize(rows, 5)

    assert result["assetIdsCensused"] == 5
    assert result["structuralVrmAssets"] == 3
    assert result["structuralVrmRate"] == 0.6
    assert result["firstStructuralVrmAssetId"] == 0
    assert result["lastStructuralVrmAssetId"] == 4
    assert result["missing404Assets"] == 1
    assert result["missing404Ranges"] == [{"start": 2, "end": 2, "count": 1}]
    assert result["otherErrorAssets"] == 1
    assert result["otherErrorRanges"] == [{"start": 3, "end": 3, "count": 1}]
    assert result["structuralVrmRanges"] == [
        {"start": 0, "end": 1, "count": 2},
        {"start": 4, "end": 4, "count": 1},
    ]
