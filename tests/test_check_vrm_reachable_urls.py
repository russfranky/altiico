from scripts.check_vrm_reachable import concrete_url


def test_prefers_valid_concrete_url():
    row = {
        "vrm_url_https": "https://cdn.example/avatar.vrm",
        "vrm_url_pattern": "https://cdn.example/{id}.vrm",
    }
    assert concrete_url(row, "9") == "https://cdn.example/avatar.vrm"


def test_rejects_descriptive_https_value_and_uses_valid_pattern():
    row = {
        "vrm_url_https": "https://example.test (same VRM for all tokens)",
        "vrm_url_pattern": "cdn.example/{id}.vrm",
    }
    assert concrete_url(row, "42") == "https://cdn.example/42.vrm"


def test_allstarz_style_descriptive_pattern_is_not_network_target():
    row = {
        "vrm_url_https": "",
        "vrm_url_pattern": "https://allstarz.world (same VRM for all tokens)",
    }
    assert concrete_url(row) is None


def test_deyes_style_placeholder_prose_is_not_network_target():
    row = {
        "vrm_url_https": "",
        "vrm_url_pattern": "https://ipfs per-token",
    }
    assert concrete_url(row) is None


def test_substitutes_supported_http_template_tokens():
    assert concrete_url(
        {"vrm_url_https": "", "vrm_url_pattern": "https://cdn.example/{token_id}.vrm"},
        "123",
    ) == "https://cdn.example/123.vrm"
    assert concrete_url(
        {"vrm_url_https": "", "vrm_url_pattern": "https://cdn.example/%d.vrm"},
        "7",
    ) == "https://cdn.example/7.vrm"


def test_substitutes_ipfs_template_without_forcing_http_gateway():
    row = {
        "vrm_url_https": "",
        "vrm_url_pattern": "ipfs://bafybeigdyrzt/{id}.vrm",
    }
    assert concrete_url(row, "5") == "ipfs://bafybeigdyrzt/5.vrm"


def test_rejects_unresolved_or_malformed_templates():
    assert concrete_url(
        {"vrm_url_https": "", "vrm_url_pattern": "https://cdn.example/{edition}.vrm"}
    ) is None
    assert concrete_url(
        {"vrm_url_https": "", "vrm_url_pattern": "not a url at all"}
    ) is None


def test_allows_scheme_less_concrete_host_path():
    row = {
        "vrm_url_https": "",
        "vrm_url_pattern": "cdn.example/static/avatar.vrm",
    }
    assert concrete_url(row) == "https://cdn.example/static/avatar.vrm"
