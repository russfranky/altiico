import asyncio
import sqlite3
from pathlib import Path

from scripts.catalog_contract_scope import collection_contract_rows
from scripts.enumerate_moralis_vrm_inventory import scan_collection


PRIMARY = "0x0000000000000000000000000000000000000001"
MIGRATED = "0x0000000000000000000000000000000000000002"


class ContractAwareMoralis:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    async def collection_nfts(self, chain, contract, *, limit=100, cursor=None):
        self.calls.append((chain, contract, limit, cursor))
        return self.payloads[(contract, cursor)]


def nft(token_id, url=None):
    metadata = {"name": f"Avatar #{token_id}"}
    if url:
        metadata["model"] = url
    return {
        "token_id": str(token_id),
        "token_uri": f"ipfs://metadata/{token_id}.json",
        "normalized_metadata": metadata,
    }


def test_contract_scope_uses_secondary_contract_table_rows(tmp_path: Path):
    db = tmp_path / "catalog.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE collections (
            id TEXT PRIMARY KEY, name TEXT, tier TEXT, chain TEXT, contract TEXT,
            avatar_count INTEGER, total_supply INTEGER, max_supply INTEGER
        );
        CREATE TABLE contracts (
            collection_id TEXT, address TEXT, chain TEXT, token_standard TEXT,
            is_primary INTEGER, PRIMARY KEY (collection_id,address)
        );
        """
    )
    conn.execute(
        "INSERT INTO collections VALUES (?,?,?,?,?,?,?,?)",
        ("demo", "Demo", "C", "ethereum", PRIMARY, 1, 1, 1),
    )
    conn.executemany(
        "INSERT INTO contracts VALUES (?,?,?,?,?)",
        [
            ("demo", PRIMARY, "ethereum", "ERC-721", 1),
            ("demo", MIGRATED, "ethereum", "ERC-721", 0),
        ],
    )
    conn.commit()

    rows = collection_contract_rows(conn)
    conn.close()

    assert len(rows) == 1
    assert [item["address"] for item in rows[0]["contracts"]] == [PRIMARY, MIGRATED]


def test_multi_contract_inventory_requires_every_contract_to_be_complete():
    row = {
        "id": "demo",
        "name": "Demo",
        "tier": "C",
        "chain": "ethereum",
        "contract": PRIMARY,
        "avatar_count": 1,
        "total_supply": 1,
        "max_supply": 1,
        "contracts": [
            {"address": PRIMARY, "chain": "ethereum", "is_primary": True},
            {"address": MIGRATED, "chain": "ethereum", "is_primary": False},
        ],
    }
    client = ContractAwareMoralis(
        {
            (PRIMARY, None): {
                "total": 1,
                "cursor": None,
                "result": [nft(1, "https://cdn.test/legacy.vrm")],
            },
            (MIGRATED, None): {
                "total": 1,
                "cursor": None,
                "result": [nft(1, "https://cdn.test/migrated.vrm")],
            },
        }
    )

    result = asyncio.run(scan_collection(client, row))

    assert result["contractsScanned"] == 2
    assert result["metadataComplete"] is True
    assert result["tokensEnumerated"] == 2
    assert result["vrmUrls"] == [
        "https://cdn.test/legacy.vrm",
        "https://cdn.test/migrated.vrm",
    ]
    assert {call[1] for call in client.calls} == {PRIMARY, MIGRATED}


def test_one_incomplete_migration_contract_fails_collection_completeness():
    row = {
        "id": "demo",
        "name": "Demo",
        "tier": "C",
        "chain": "ethereum",
        "contract": PRIMARY,
        "avatar_count": 1,
        "total_supply": 1,
        "max_supply": 1,
        "contracts": [
            {"address": PRIMARY, "chain": "ethereum", "is_primary": True},
            {"address": MIGRATED, "chain": "ethereum", "is_primary": False},
        ],
    }
    client = ContractAwareMoralis(
        {
            (PRIMARY, None): {
                "total": 1,
                "cursor": None,
                "result": [nft(1, "https://cdn.test/legacy.vrm")],
            },
            (MIGRATED, None): {
                "total": 1,
                "cursor": None,
                "result": [nft(1)],
            },
        }
    )

    result = asyncio.run(scan_collection(client, row))

    assert result["contractsScanned"] == 2
    assert result["metadataComplete"] is False
    assert result["tokensMissingVrmLinks"] == 1
