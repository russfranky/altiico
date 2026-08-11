from scripts.audit_vrm_links import _looks_like_url, _looks_like_vrm


def test_rejects_descriptive_pseudo_urls_with_spaces():
    assert not _looks_like_url("https://allstarz.world (same vrm for all tokens)/")
    assert not _looks_like_url("https://digitaloceanspaces per-token/")
    assert not _looks_like_url("https://ipfs per-token/")


def test_accepts_supported_concrete_urls():
    assert _looks_like_url("https://example.com/avatar.vrm")
    assert _looks_like_url("ipfs://bafybeiexample/avatar.vrm")
    assert _looks_like_url("ar://exampleTransactionId/avatar.vrm")


def test_vrm_detection_keeps_extensionless_and_glb_model_pointers():
    assert _looks_like_vrm("https://example.com/avatar.vrm")
    assert _looks_like_vrm("https://example.com/model/123", "model_file_url")
    assert _looks_like_vrm("https://example.com/avatar.glb", "vrm_url")
