from scripts.discover_opensea_nfts import is_junk_lead, lead_score


def test_known_marketplace_slugs_are_junk():
    assert is_junk_lead({"collection": "ens", "name": "vitalik.eth"})
    assert is_junk_lead({"collection": "courtyard-nft", "name": "Card"})
    assert is_junk_lead({"collection": "uniswap-v3-positions", "name": "UNI-V3"})
    assert is_junk_lead({"collection": "superrare", "name": "Artwork"})
    assert is_junk_lead({"collection": "something-new", "name": "alice.eth"})
    assert not is_junk_lead({"collection": "clonex", "name": "CloneX #1"})


def test_vrm_specific_queries_rank_above_generic_hits():
    junkish = {
        "key": "a",
        "collection": "random-pfp",
        "name": "Token 1",
        "queries": {"3D avatar"},
    }
    vrm = {
        "key": "b",
        "collection": "ready-player-avatars",
        "name": "VRM Avatar #9",
        "queries": {"VRM avatar", "VRMC_vrm"},
    }
    assert lead_score(vrm) > lead_score(junkish)
