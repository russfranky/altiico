import json

from scripts.audit_dickbuttverse_onchain_identity import (
    decode_abi_string,
    decode_address,
    encode_uint_call,
    model_urls,
    proven_token_ids,
    sample_ids,
    url_numeric_tail,
)


def abi_string(value: str) -> str:
    raw = value.encode()
    padded = raw + b"\0" * ((32 - len(raw) % 32) % 32)
    payload = (32).to_bytes(32, "big") + len(raw).to_bytes(32, "big") + padded
    return "0x" + payload.hex()


def test_uint_call_encoding():
    assert encode_uint_call("c87b56dd", 1696) == "0xc87b56dd" + format(1696, "064x")


def test_abi_decoders():
    address = "1234567890abcdef1234567890abcdef12345678"
    assert decode_address("0x" + "0" * 24 + address) == "0x" + address
    assert decode_address("0x" + "0" * 64) is None
    url = "https://example.test/json/3225.json"
    assert decode_abi_string(abi_string(url)) == url


def test_numeric_tail_requires_final_numeric_path_component():
    assert url_numeric_tail("https://example.test/json/3225.json") == 3225
    assert url_numeric_tail("https://example.test/vrm/3225.vrm") == 3225
    assert url_numeric_tail("https://example.test/3225/preview.png") is None


def test_model_url_discovery_is_recursive_and_suffix_bound():
    metadata = {
        "image": "https://example.test/7.png",
        "nested": {
            "vrm": "https://example.test/vrm/7.vrm",
            "other": ["ipfs://cid/7.glb", "hello"],
        },
    }
    found = {item["url"] for item in model_urls(metadata)}
    assert found == {"https://example.test/vrm/7.vrm", "ipfs://cid/7.glb"}


def test_proven_ids_and_sample_selection(tmp_path):
    path = tmp_path / "reconciliation.json"
    path.write_text(
        json.dumps(
            {
                "reconciled": [
                    {"catalogId": "dickbuttverse", "tokenId": "0"},
                    {"catalogId": "dickbuttverse", "tokenId": "1000"},
                    {"catalogId": "other", "tokenId": "9999"},
                ]
            }
        )
    )
    proven = proven_token_ids(path)
    assert proven == {0, 1000}
    selected = sample_ids(proven, [5306], 32)
    assert 0 in selected
    assert 1000 in selected
    assert 1696 in selected
    assert 3225 in selected
    assert 4914 in selected
    assert 5306 in selected
    assert 5349 in selected
    assert 5362 in selected
