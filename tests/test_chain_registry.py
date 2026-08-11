from scripts.chain_registry import CHAINS, EVM_RPCS, OPENSEA_CHAIN_MAP, get_chain


def test_chain_ids_are_unique():
    ids = [spec.chain_id for spec in CHAINS.values()]
    assert len(ids) == len(set(ids))


def test_every_chain_has_rpc_and_explorer():
    for key, spec in CHAINS.items():
        assert spec.key == key
        assert spec.rpc_urls
        assert all(url.startswith("https://") for url in spec.rpc_urls)
        assert spec.explorer_url.startswith("https://")
        assert EVM_RPCS[key] == spec.rpc_urls


def test_robinhood_mainnet_configuration():
    chain = get_chain("robinhood")
    assert chain.chain_id == 4663
    assert chain.rpc_urls == ("https://rpc.mainnet.chain.robinhood.com",)
    assert chain.explorer_url == "https://robinhoodchain.blockscout.com"
    assert chain.blockscout_api == "https://robinhoodchain.blockscout.com/api/v2"


def test_opensea_map_only_contains_verified_aliases():
    assert "ethereum" in OPENSEA_CHAIN_MAP
    assert "polygon" in OPENSEA_CHAIN_MAP
    assert "robinhood" not in OPENSEA_CHAIN_MAP
