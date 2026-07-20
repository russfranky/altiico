"""Tests for OpenSea shared-storefront collection resolution.

The shared storefront contract 0x495f947276749ce646f68ac8c248420045cb7b5e is an
ERC-1155 contract that hosts assets from many different OpenSea collections
(pixelbeasts, chametheon, cyberanimedoll-avatar). The contract address alone
cannot identify a collection, so the resolver requires a token_id or slug.

No live API calls are made — all OpenSeaClient methods are mocked.
"""

from __future__ import annotations

import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make the repo root importable so `scripts.*` resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.resolve_opensea_collections import (  # noqa: E402
    resolve,
    load_overrides,
)

SHARED_STOREFRONT = "0x495f947276749ce646f68ac8c248420045cb7b5e"
CYBERBROKERS = "0x892848074ddea461a15f337250da3ce55580ca85"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --------------------------------------------------------------------------- 1


def test_contract_only_shared_storefront_raises():
    client = MagicMock()
    client.get_nft = AsyncMock()

    with pytest.raises(ValueError):
        _run(
            resolve(
                client,
                chain="ethereum",
                contract=SHARED_STOREFRONT,
                token_id=None,
                slug=None,
            )
        )
    client.get_nft.assert_not_called()


# --------------------------------------------------------------------------- 2


def test_slug_override_short_circuits():
    client = MagicMock()
    client.get_nft = AsyncMock()

    result = _run(
        resolve(
            client,
            chain="ethereum",
            contract=SHARED_STOREFRONT,
            token_id=None,
            slug="pixelbeasts",
        )
    )

    assert result["opensea_slug"] == "pixelbeasts"
    assert result["resolution_source"] in ("opensea-slug", "override")
    client.get_nft.assert_not_called()


# --------------------------------------------------------------------------- 3


def test_token_id_resolves_to_pixelbeasts():
    client = MagicMock()
    client.get_nft = AsyncMock(
        return_value={"nft": {"collection": "pixelbeasts", "identifier": "123"}}
    )

    result = _run(
        resolve(
            client,
            chain="ethereum",
            contract=SHARED_STOREFRONT,
            token_id="123",
        )
    )

    assert result["opensea_slug"] == "pixelbeasts"
    assert result["resolution_source"] == "opensea-token"
    client.get_nft.assert_awaited_once()


# --------------------------------------------------------------------------- 4


def test_token_id_resolves_to_chametheon():
    client = MagicMock()
    client.get_nft = AsyncMock(
        return_value={"nft": {"collection": "chametheon", "identifier": "456"}}
    )

    result = _run(
        resolve(
            client,
            chain="ethereum",
            contract=SHARED_STOREFRONT,
            token_id="456",
        )
    )

    assert result["opensea_slug"] == "chametheon"
    assert result["resolution_source"] == "opensea-token"
    client.get_nft.assert_awaited_once()


# --------------------------------------------------------------------------- 5


def test_token_id_resolves_to_cyberanimedoll():
    client = MagicMock()
    client.get_nft = AsyncMock(
        return_value={
            "nft": {"collection": "cyberanimedoll-avatar", "identifier": "789"}
        }
    )

    result = _run(
        resolve(
            client,
            chain="ethereum",
            contract=SHARED_STOREFRONT,
            token_id="789",
        )
    )

    assert result["opensea_slug"] == "cyberanimedoll-avatar"
    assert result["resolution_source"] == "opensea-token"
    client.get_nft.assert_awaited_once()


# --------------------------------------------------------------------------- 6


def test_same_contract_different_tokens_different_slugs():
    cases = [
        ("123", {"nft": {"collection": "pixelbeasts", "identifier": "123"}}),
        ("456", {"nft": {"collection": "chametheon", "identifier": "456"}}),
        ("789", {"nft": {"collection": "cyberanimedoll-avatar", "identifier": "789"}}),
    ]
    slugs = []
    for token_id, nft_resp in cases:
        client = MagicMock()
        client.get_nft = AsyncMock(return_value=nft_resp)
        result = _run(
            resolve(
                client,
                chain="ethereum",
                contract=SHARED_STOREFRONT,
                token_id=token_id,
            )
        )
        slugs.append(result["opensea_slug"])

    assert len(set(slugs)) == 3, f"expected 3 distinct slugs, got {slugs}"
    assert "pixelbeasts" in slugs
    assert "chametheon" in slugs
    assert "cyberanimedoll-avatar" in slugs


# --------------------------------------------------------------------------- 7


def test_overrides_yaml_loaded():
    overrides = load_overrides()

    assert "shared_storefront_contracts" in overrides
    assert SHARED_STOREFRONT in overrides["shared_storefront_contracts"]
    collections = overrides.get("collections", [])
    assert len(collections) == 3, f"expected 3 collection overrides, got {len(collections)}"


# --------------------------------------------------------------------------- 8


def test_non_shared_storefront_contract_ok():
    client = MagicMock()
    client.get_nft = AsyncMock(
        return_value={"nft": {"collection": "some-slug"}}
    )

    result = _run(
        resolve(
            client,
            chain="ethereum",
            contract=CYBERBROKERS,
            token_id="1",
        )
    )

    assert result["opensea_slug"] == "some-slug"
    client.get_nft.assert_awaited_once()
