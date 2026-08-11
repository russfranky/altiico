"""Canonical chain configuration for discovery adapters.

Keep chain identity, public RPCs, explorers, and optional marketplace aliases in
one place so adding a new EVM chain does not require copy/paste configuration in
every crawler.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChainSpec:
    key: str
    chain_id: int
    rpc_urls: tuple[str, ...]
    explorer_url: str
    blockscout_api: str | None = None
    opensea_name: str | None = None


CHAINS: dict[str, ChainSpec] = {
    "ethereum": ChainSpec(
        "ethereum", 1,
        ("https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"),
        "https://etherscan.io",
        "https://eth.blockscout.com/api/v2",
        "ethereum",
    ),
    "polygon": ChainSpec(
        "polygon", 137,
        ("https://polygon-bor-rpc.publicnode.com", "https://polygon-rpc.com"),
        "https://polygonscan.com",
        None,
        "matic",
    ),
    "base": ChainSpec(
        "base", 8453,
        ("https://base-rpc.publicnode.com", "https://mainnet.base.org"),
        "https://basescan.org",
        None,
        "base",
    ),
    "optimism": ChainSpec(
        "optimism", 10,
        ("https://optimism-rpc.publicnode.com", "https://mainnet.optimism.io"),
        "https://optimistic.etherscan.io",
        None,
        "optimism",
    ),
    "arbitrum": ChainSpec(
        "arbitrum", 42161,
        ("https://arbitrum-one-rpc.publicnode.com",),
        "https://arbiscan.io",
        None,
        "arbitrum",
    ),
    "shape": ChainSpec(
        "shape", 360,
        ("https://mainnet.shape.network",),
        "https://shapescan.xyz",
        None,
        "shape",
    ),
    "ape_chain": ChainSpec(
        "ape_chain", 33139,
        ("https://apechain.calderachain.xyz/http",),
        "https://apescan.io",
    ),
    "robinhood": ChainSpec(
        "robinhood", 4663,
        ("https://rpc.mainnet.chain.robinhood.com",),
        "https://robinhoodchain.blockscout.com",
        "https://robinhoodchain.blockscout.com/api/v2",
        None,
    ),
}

EVM_RPCS: dict[str, tuple[str, ...]] = {
    key: spec.rpc_urls for key, spec in CHAINS.items()
}

OPENSEA_CHAIN_MAP: dict[str, str] = {
    key: spec.opensea_name
    for key, spec in CHAINS.items()
    if spec.opensea_name
}


def get_chain(key: str) -> ChainSpec:
    try:
        return CHAINS[key.lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported chain: {key}") from exc
