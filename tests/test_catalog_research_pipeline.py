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
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT,
            chain TEXT,
            contract TEXT,
            opensea_slug TEXT,
            release_date TEXT,
            vrm_param TEXT,
            vrm_url_pattern TEXT,
            avatar_count INTEGER,
            vrm_license TEXT,
            commercial_use TEXT,
            allowed_user TEXT,
            redistribution TEXT,
            license_category TEXT,
            description TEXT,
            curated_description TEXT,
            notes TEXT,
            source TEXT,
            discord_url TEXT,
            twitter_username TEXT,
            image_url TEXT,
            banner_image_url TEXT,
            sample_nft_image TEXT,
            vrm_url_https TEXT,
            total_supply INTEGER,
            max_supply INTEGER,
            project_url TEXT,
            vrm_check_status TEXT,
            vrm_check_url TEXT
        );
        CREATE TABLE contracts (
            collection_id TEXT,
            address TEXT,
            chain TEXT,
            is_primary INTEGER,
            PRIMARY KEY (collection_id,address)
        );
        CREATE TABLE avatars (
            id TEXT PRIMARY KEY,
            collection_id TEXT,
            model_file_url TEXT,
            is_public INTEGER
        );
        """
    )
    conn.commit()
    conn.close()


def evidence(source="https://example.test/source"):
    return [{"source": source, "note": "authoritative test evidence"}]


def test_markdown_parser_recovers_tables_from_actual_header_row():
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
    leads = collection_leads(markdown)
    by_name = {lead["name"]: lead for lead in leads}

    assert set(by_name) == {"Super Yetis", "100Avatars R1", "3D Anvil"}
    assert by_name["Super Yetis"]["id"] == "superyeti"
    assert by_name["Super Yetis"]["tier"] == "C"
    assert by_name["100Avatars R1"]["tier"] == "arweave"
    assert by_name["100Avatars R1"]["avatar_count"] == 100
    assert by_name["3D Anvil"]["tier"] == "infra"


def test_markdown_reconciliation_inserts_missing_source_identity(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    markdown = tmp_path / "catalog.md"
    markdown.write_text(
        """
## Tier C — WIP

| Collection | OpenSea | Notes |
| --- | --- | --- |
| Super Yetis | opensea.io/collection/superyeti | WIP |
""",
        encoding="utf-8",
    )
    report = reconcile_markdown(db, markdown, tmp_path / "report.json")
    assert report["summary"]["inserted"] == 1

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT id,name,tier,opensea_slug FROM collections"
    ).fetchone()
    conn.close()
    assert row == ("superyeti", "Super Yetis", "C", "superyeti")


def test_markdown_reconciliation_matches_existing_name_without_duplication(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO collections (id,name,tier,chain,source) VALUES (?,?,?,?,?)",
        ("super-yetis", "Super Yetis", "C", "ethereum", "manual"),
    )
    conn.commit()
    conn.close()

    markdown = tmp_path / "catalog.md"
    markdown.write_text(
        """
## Tier C — WIP

| Collection | OpenSea | Notes |
| --- | --- | --- |
| Super Yetis | opensea.io/collection/superyeti | WIP |
""",
        encoding="utf-8",
    )
    report = reconcile_markdown(db, markdown, tmp_path / "report.json")
    assert report["summary"]["inserted"] == 0
    assert report["summary"]["matched"] == 1

    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT id,opensea_slug FROM collections").fetchall()
    conn.close()
    assert rows == [("super-yetis", "superyeti")]


def test_materializer_inserts_research_only_sunset_collection_and_keeps_access_separate(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    research_path = tmp_path / "research.json"
    research_path.write_text(
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
                            "value": "sunset",
                            "state": "sunset",
                            "evidence": evidence(),
                        },
                        "storage": {
                            "value": "ipfs",
                            "scope": "nft_metadata_and_images",
                            "evidence": evidence(),
                        },
                        "vrm_inventory": {
                            "state": "unrecoverable",
                            "coverage": "unrecoverable",
                            "urls": [],
                            "evidence": evidence(),
                        },
                        "ip_rights": {
                            "value": "commercial_rights_reported",
                            "summary": "Commercial rights were reported, exact terms unrecovered.",
                            "state": "unrecoverable",
                            "evidence": evidence(),
                        },
                        "file_access": {
                            "mode": "unavailable",
                            "state": "unrecoverable",
                            "requires_ownership": None,
                            "evidence": evidence(),
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    report = materialize_research(db, research_path)
    assert report["inserted"] == 1

    conn = sqlite3.connect(db)
    row = conn.execute(
        """
        SELECT name,project_status,short_description,storage_types,
               vrm_inventory_state,vrm_inventory_complete,
               file_access_mode,file_access_requires_ownership,ip_rights_summary
        FROM collections WHERE id='super-yetis'
        """
    ).fetchone()
    contract = conn.execute(
        "SELECT address FROM contracts WHERE collection_id='super-yetis'"
    ).fetchone()[0]
    evidence_rows = conn.execute(
        "SELECT COUNT(*) FROM catalog_research_evidence WHERE collection_id='super-yetis'"
    ).fetchone()[0]
    conn.close()

    assert row[0] == "Super Yetis"
    assert row[1] == "sunset"
    assert row[2].startswith("A historical")
    assert json.loads(row[3]) == ["ipfs"]
    assert row[4] == "unrecoverable"
    assert row[5] == 1
    assert row[6] == "unavailable"
    assert row[7] is None
    assert "Commercial rights were reported" in row[8]
    assert contract == "0x3f0785095a660fee131eebcd5aa243e529c21786"
    assert evidence_rows >= 5


def test_materializer_requires_evidence_before_manual_social_or_media_override(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO collections (id,name,tier,chain) VALUES ('demo','Demo','C','ethereum')"
    )
    conn.commit()
    conn.close()

    research_path = tmp_path / "research.json"
    research_path.write_text(
        json.dumps(
            {
                "collections": {
                    "demo": {
                        "banner": {"value": "https://example.test/banner.png"},
                        "discord": {"value": "https://discord.gg/demo"},
                        "x": {"value": "https://x.com/demo"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    materialize_research(db, research_path)

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT banner_image_url,discord_url,twitter_username FROM collections WHERE id='demo'"
    ).fetchone()
    conn.close()
    assert row == (None, None, None)


def inventory_row(**updates):
    row = {
        "id": "demo",
        "name": "Demo",
        "avatar_count": 2,
        "total_supply": 2,
        "max_supply": 2,
        "vrm_url_https": "",
        "vrm_url_pattern": "",
    }
    row.update(updates)
    return row


def test_inventory_one_sample_never_implies_collection_complete(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO collections (id,name,avatar_count,total_supply,max_supply) VALUES ('demo','Demo',2,2,2)"
    )
    conn.execute(
        "INSERT INTO avatars (id,collection_id,model_file_url,is_public) VALUES ('1','demo','ipfs://bafy/1.vrm',1)"
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM collections WHERE id='demo'").fetchone())
    result = inventory_for(conn, row, {})
    conn.close()

    assert result["state"] == "partial"
    assert result["complete"] is False
    assert result["enumerated_urls"] == 1


def test_inventory_authoritative_token_template_can_be_exhaustive(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = inventory_row(vrm_url_pattern="ipfs://bafy/{id}.vrm")
    result = inventory_for(conn, row, {})
    conn.close()

    assert result["state"] == "complete_template"
    assert result["complete"] is True
    assert result["url_template"] == "ipfs://bafy/{id}.vrm"


def test_inventory_descriptive_pseudo_url_is_not_evidence(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = inventory_row(vrm_url_pattern="allstarz.world (same VRM for all tokens)")
    result = inventory_for(conn, row, {})
    conn.close()

    assert result["state"] == "unknown"
    assert result["complete"] is False
    assert result["url_template"] is None


def test_inventory_terminal_research_state_is_explicit_not_fabricated(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = inventory_row()
    research = {
        "vrm_inventory": {
            "state": "unrecoverable",
            "urls": [],
            "evidence": evidence(),
        },
        "file_access": {
            "mode": "unavailable",
            "requires_ownership": None,
            "evidence": evidence(),
        },
    }
    result = inventory_for(conn, row, research)
    conn.close()

    assert result["state"] == "unrecoverable"
    assert result["complete"] is True
    assert result["terminal"] is True
    assert result["urls"] == []
    assert result["access"]["mode"] == "unavailable"
    assert result["access"]["requires_ownership"] is None


def test_inventory_export_reports_partial_and_terminal_states(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO collections (id,name,avatar_count,total_supply,max_supply) VALUES (?,?,?,?,?)",
        [("partial", "Partial", 2, 2, 2), ("terminal", "Terminal", 2, 2, 2)],
    )
    conn.execute(
        "INSERT INTO avatars (id,collection_id,model_file_url,is_public) VALUES ('p1','partial','https://cdn.test/1.vrm',1)"
    )
    conn.commit()
    conn.close()

    research_path = tmp_path / "research.json"
    research_path.write_text(
        json.dumps(
            {
                "collections": {
                    "terminal": {
                        "vrm_inventory": {
                            "state": "unrecoverable",
                            "evidence": evidence(),
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "inventory.json"
    payload = export_inventory(db, research_path, output)

    assert payload["summary"]["partial"] == 1
    assert payload["summary"]["unknown"] == 0
    assert payload["summary"]["complete"] == 1
    assert json.loads(output.read_text())["schema"] == "vrm-catalog-inventory-v1"
