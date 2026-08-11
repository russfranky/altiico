from scripts.crawler.uri import canonicalize_uri


def test_custom_pinata_path_gateway_canonicalizes_to_ipfs():
    cid = "QmZYVVP2XMNK2mjcrac6zyocvAU9xuEupZ4zYuoPVuimr7"
    url = f"https://phettaverse.mypinata.cloud/ipfs/{cid}/borgormachinelowpoly.vrm"
    assert canonicalize_uri(url) == f"ipfs://{cid}/borgormachinelowpoly.vrm"


def test_unrelated_custom_host_is_not_rewritten_as_ipfs():
    url = "https://example.com/ipfs/QmExample/avatar.vrm"
    assert canonicalize_uri(url) == url
