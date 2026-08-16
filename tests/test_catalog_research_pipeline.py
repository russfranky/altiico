import json
import sqlite3
from pathlib import Path

from scripts.export_vrm_inventory import inventory_for, run as export_inventory
from scripts.materialize_catalog_research import run as materialize_research
from scripts.reconcile_markdown_catalog_sources import collection_leads, run as reconcile_markdown


def make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE collections (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, tier TEXT, chain TEXT,
            contract TEXT, opensea_slug TEXT, release_date TEXT, vrm_param TEXT,
            vrm_url_pattern TEXT, avatar_count INTEGER, vrm_license TEXT,
            commercial_use TEXT, allowed_user TEXT, redistribution TEXT,
            license_category TEXT, description TEXT, curated_description TEXT,
            notes TEXT, source TEXT, discord_url TEXT, twitter_username TEXT,
            image_url TEXT, banner_image_url TEXT, sample_nft_image TEXT,
            vrm_url_https TEXT, total_supply INTEGER, max_supply INTEGER,
            project_url TEXT, vrm_check_status TEXT, vrm_check_url TEXT
        );
        CREATE TABLE contracts (
            collection_id TEXT, address TEXT, chain TEXT, is_primary INTEGER,
            PRIMARY KEY (collection_id,address)
        );
        CREATE TABLE avatars (
            id TEXT PRIMARY KEY, collection_id TEXT,
            model_file_url TEXT, is_public INTEGER
        );
        """
    )
    conn.commit()
    conn.close()


def evidence(source="https://example.test/source"):
    return [{"source": source, "note": "authoritative test evidence"}]


def test_markdown_parser_recovers_tables_from_real_header_rows():
    markdown = """
## Tier C — WIP / proof-of-concept / community-led

| Collection | OpenSea | Notes |
| --- | --- | --- |
| Super Yetis | opensea.io/collection/superyeti | WIP, Q/A |

## Arweave-native VRM collections (not NFTs, but CC0 VRM avatar registries)

| Collection | Count | License | Storage | Sample |
| --- | --- | --- | --- | --- |
| 100Avatars R1 | 100 | CC0 | Arweave | arweave sample |

## Non-Ethereum VRM infrastructure (no canonical collection list yet)

| Platform | Chain | Storage | Notes |
| --- | --- | --- | --- |
| 3D Anvil | Solana | Arweave via Irys | VRM launchpad |
"""
    by_name = {lead["name"]: lead for lead in collection_leads(markdown)}
    assert set(by_name) == {"Super Yetis", "100Avatars R1", "3D Anvil"}
    assert by_name["Super Yetis"]["tier"] == "C"
    assert by_name["100Avatars R1"]["tier"] == "arweave"
    assert by_name["100Avatars R1"]["avatar_count"] == 100
    assert by_name["3D Anvil"]["tier"] == "infra"


def test_markdown_reconciliation_matches_existing_identity_without_duplicate(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO collections (id,name,tier,chain,source) VALUES (?,?,?,?,?)",
        ("super-yetis", "Super Yetis", "C", "ethereum", "manual"),
    )
    conn.commit()
    conn.close()
    source = tmp_path / "catalog.md"
    source.write_text(
        """
## Tier C — WIP

| Collection | OpenSea | Notes |
| --- | --- | --- |
| Super Yetis | opensea.io/collection/superyeti | WIP |
""",
        encoding="utf-8",
    )
    report = reconcile_markdown(db, source, tmp_path / "report.json")
    assert report["summary"]["inserted"] == 0
    assert report["summary"]["matched"] == 1
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT id,opensea_slug FROM collections").fetchall()
    conn.close()
    assert rows == [("super-yetis", "superyeti")]


def test_materializer_keeps_sunset_ip_rights_and_access_separate(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    research = tmp_path / "research.json"
    research.write_text(
        json.dumps(
            {
                "collections": {
                    "super-yetis": {
                        "identity": {
                            "name": "Super Yetis",
                            "tier": "C",
                            "chain": "ethereum",
                            "contract": "0x3f0785095a660fee131eebcd5aa243e529c21786",
                            "opensea_slug": "superyeti",
                        },
                        "short_description": {
                            "value": "A historical full-body 3D yeti avatar project.",
                            "evidence": evidence(),
                        },
                        "project_status": {
                            "value": "sunset", "state": "sunset", "evidence": evidence()
                        },
                        "storage": {
                            "value": "ipfs", "scope": "nft_metadata_and_images", "evidence": evidence()
                        },
                        "vrm_inventory": {
                            "state": "unrecoverable", "coverage": "unrecoverable",
                            "urls": [], "evidence": evidence()
                        },
                        "ip_rights": {
                            "value": "commercial_rights_reported",
                            "summary": "Commercial rights reported; exact terms unrecovered.",
                            "state": "unrecoverable", "evidence": evidence()
                        },
                        "file_access": {
                            "mode": "unavailable", "state": "unrecoverable",
                            "requires_ownership": None, "evidence": evidence()
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    report = materialize_research(db, research)
    assert report["inserted"] == 1
    conn = sqlite3.connect(db)
    row = conn.execute(
        """
        SELECT project_status,short_description,storage_types,
               vrm_inventory_state,vrm_inventory_complete,
               file_access_mode,file_access_requires_ownership,ip_rights_summary
        FROM collections WHERE id='super-yetis'
        """
    ).fetchone()
    evidence_rows = conn.execute(
        "SELECT COUNT(*) FROM catalog_research_evidence WHERE collection_id='super-yetis'"
    ).fetchone()[0]
    conn.close()
    assert row[0] == "sunset"
    assert row[1].startswith("A historical")
    assert json.loads(row[2]) == ["ipfs"]
    assert row[3] == "unrecoverable" and row[4] == 1
    assert row[5] == "unavailable" and row[6] is None
    assert "Commercial rights" in row[7]
    assert evidence_rows >= 5


def inventory_row(**updates):
    row = {
        "id": "demo", "name": "Demo", "avatar_count": 2,
        "total_supply": 2, "max_supply": 2,
        "vrm_url_https": "", "vrm_url_pattern": "",
    }
    row.update(updates)
    return row


def test_one_sample_link_never_implies_complete_inventory(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO collections (id,name,avatar_count,total_supply,max_supply) VALUES ('demo','Demo',2,2,2)"
    )
    conn.execute(
        "INSERT INTO avatars VALUES ('1','demo','ipfs://bafy/1.vrm',1)"
    )
    conn.commit(); conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM collections WHERE id='demo'").fetchone())
    result = inventory_for(conn, row, {})
    conn.close()
    assert result["state"] == "partial"
    assert result["complete"] is False
    assert result["enumerated_urls"] == 1


def test_token_template_is_only_a_candidate_until_expanded(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    result = inventory_for(conn, inventory_row(vrm_url_pattern="ipfs://bafy/{id}.vrm"), {})
    conn.close()
    assert result["state"] == "unknown"
    assert result["complete"] is False
    assert result["candidate_url_template"] == "ipfs://bafy/{id}.vrm"


def test_descriptive_pseudo_url_is_not_inventory_evidence(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    result = inventory_for(conn, inventory_row(vrm_url_pattern="allstarz.world (same VRM for all tokens)"), {})
    conn.close()
    assert result["state"] == "unknown"
    assert result["candidate_url_template"] is None


def test_cursor_exhausted_moralis_links_can_make_inventory_complete(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    result = inventory_for(
        conn,
        inventory_row(),
        {},
        {
            "metadataComplete": True,
            "tokensEnumerated": 2,
            "vrmUrls": ["https://cdn.test/1.vrm", "https://cdn.test/2.vrm"],
        },
    )
    conn.close()
    assert result["state"] == "complete"
    assert result["complete"] is True
    assert result["coverage_source"] == "moralis_cursor_exhausted"
    assert result["urls"] == ["https://cdn.test/1.vrm", "https://cdn.test/2.vrm"]


def test_terminal_research_state_is_explicit_not_fabricated(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    research = {
        "storage": {"value": "ipfs", "scope": "nft_metadata", "evidence": evidence()},
        "vrm_inventory": {"state": "unrecoverable", "urls": [], "evidence": evidence()},
        "file_access": {"mode": "unavailable", "requires_ownership": None, "evidence": evidence()},
    }
    result = inventory_for(conn, inventory_row(), research)
    conn.close()
    assert result["state"] == "unrecoverable"
    assert result["complete"] is True and result["terminal"] is True
    assert result["urls"] == []
    assert result["storage"]["types"] == ["ipfs"]
    assert result["access"]["mode"] == "unavailable"


def test_holder_gated_vrm_excludes_public_glb_sample(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    glb = "https://assets.example.test/avatar/3d/idle"
    research = {
        "vrm_inventory": {
            "state": "holder_gated",
            "urls": [],
            "evidence": evidence(),
        },
        "avatar_inventory": {
            "state": "partial",
            "assets": [{"url": glb, "format": "glb", "rigged": False}],
            "evidence": evidence(),
        },
        "file_access": {
            "mode": "holder_gated",
            "requires_ownership": True,
            "access_url": "https://example.test/vault",
            "evidence": evidence(),
        },
    }
    result = inventory_for(conn, inventory_row(vrm_url_https=glb), research)
    conn.close()
    assert glb not in result["urls"]
    assert result["state"] == "holder_gated"
    assert result["complete"] is False
    assert result["terminal"] is False
    assert result["access"]["mode"] == "holder_gated"
    assert result["access"]["requires_ownership"] is True


def test_inventory_export_schema_v2(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO collections (id,name,avatar_count,total_supply,max_supply) VALUES ('demo','Demo',1,1,1)"
    )
    conn.execute("INSERT INTO avatars VALUES ('1','demo','https://cdn.test/1.vrm',1)")
    conn.commit(); conn.close()
    research = tmp_path / "research.json"
    research.write_text(json.dumps({"collections": {}}), encoding="utf-8")
    output = tmp_path / "inventory.json"
    payload = export_inventory(db, research, output, tmp_path / "missing-moralis.json")
    assert payload["summary"]["complete"] == 1
    assert json.loads(output.read_text())["schema"] == "vrm-catalog-inventory-v2"
