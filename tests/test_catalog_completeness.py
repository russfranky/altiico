import json
import sqlite3
from pathlib import Path

from scripts.audit_catalog_completeness import (
    evaluate_collection,
    run,
    short_description,
    storage_for_urls,
)


def base_row(**updates):
    row = {
        "id": "demo",
        "name": "Demo",
        "tier": "A",
        "banner_image_url": "https://example.test/banner.png",
        "description": "A complete VRM avatar collection with a useful short description.",
        "curated_description": None,
        "discord_url": "https://discord.gg/demo",
        "twitter_username": "demovrm",
        "image_url": "https://example.test/logo.png",
        "sample_nft_image": "",
        "release_date": "2024-01-02",
        "vrm_url_https": "",
        "vrm_url_pattern": "",
        "avatar_count": 2,
        "total_supply": 2,
        "max_supply": 2,
        "vrm_license": "CC0",
        "license_category": "green",
        "allowed_user": "Everyone",
        "redistribution": "Allow",
        "vrm_check_status": None,
        "vrm_check_url": None,
    }
    row.update(updates)
    return row


def active_research():
    evidence = [{"source": "https://example.test/about", "note": "official project source"}]
    return {
        "project_status": {"value": "active", "evidence": evidence},
        "file_access": {"mode": "public", "evidence": evidence},
    }


def complete_avatar_fact():
    return {
        "rows": 2,
        "with_url": 2,
        "public_rows": 2,
        "nonpublic_rows": 0,
        "urls": [
            "ipfs://bafy/demo-1.vrm",
            "ipfs://bafy/demo-2.vrm",
        ],
    }


def complete_license_fact():
    return {
        "color": "green",
        "confidence": "high",
        "use_scope": "everyone",
        "commercial_scope": "allowed",
        "redistribute_original": "allowed",
    }


def test_requires_discord_and_x_independently():
    row = base_row(discord_url="", twitter_username="demovrm")
    result = evaluate_collection(
        row, complete_avatar_fact(), complete_license_fact(), active_research()
    )
    assert "discord" in result["missing"]
    assert "x" not in result["missing"]


def test_evidenced_absence_resolves_missing_social():
    row = base_row(discord_url="")
    research = active_research()
    research["discord"] = {
        "state": "not_available",
        "evidence": [{"source": "https://example.test", "note": "official site lists no Discord"}],
    }
    result = evaluate_collection(
        row, complete_avatar_fact(), complete_license_fact(), research
    )
    assert result["fields"]["discord"]["ok"] is True
    assert result["fields"]["discord"]["state"] == "not_available"


def test_negative_state_without_evidence_does_not_pass():
    row = base_row(discord_url="")
    research = active_research()
    research["discord"] = {"state": "not_available"}
    result = evaluate_collection(
        row, complete_avatar_fact(), complete_license_fact(), research
    )
    assert result["fields"]["discord"]["ok"] is False


def test_sunset_is_first_class_project_status():
    research = active_research()
    research["project_status"] = {
        "value": "sunset",
        "evidence": [{"source": "curator_assertion", "note": "Project is sunset"}],
    }
    result = evaluate_collection(
        base_row(), complete_avatar_fact(), complete_license_fact(), research
    )
    assert result["fields"]["project_status"]["ok"] is True
    assert result["fields"]["project_status"]["value"] == "sunset"


def test_ip_rights_do_not_imply_file_access():
    research = {"project_status": active_research()["project_status"]}
    result = evaluate_collection(
        base_row(), complete_avatar_fact(), complete_license_fact(), research
    )
    assert result["fields"]["ip_rights"]["ok"] is True
    assert result["fields"]["file_access"]["value"] == "public"

    partial_avatar = complete_avatar_fact()
    partial_avatar["rows"] = 1
    partial_avatar["with_url"] = 1
    partial_avatar["public_rows"] = 0
    partial_avatar["urls"] = ["https://example.test/one.vrm"]
    result = evaluate_collection(
        base_row(), partial_avatar, complete_license_fact(), research
    )
    assert result["fields"]["ip_rights"]["ok"] is True
    assert result["fields"]["file_access"]["ok"] is False


def test_inventory_fails_when_only_partial_links_are_known():
    avatar = complete_avatar_fact()
    avatar.update({"rows": 1, "with_url": 1, "public_rows": 1, "urls": ["ipfs://bafy/1.vrm"]})
    result = evaluate_collection(
        base_row(avatar_count=2, total_supply=2),
        avatar,
        complete_license_fact(),
        active_research(),
    )
    assert result["fields"]["vrm_inventory"]["ok"] is False
    assert result["fields"]["vrm_inventory"]["value"]["coverage"] == "partial"


def test_storage_is_derived_from_actual_vrm_links():
    assert storage_for_urls(["ipfs://bafy/a.vrm"]) == ["ipfs"]
    assert storage_for_urls(["https://arweave.net/tx"]) == ["arweave"]
    assert storage_for_urls(["https://cdn.example/a.vrm", "ipfs://bafy/a.vrm"]) == [
        "https",
        "ipfs",
    ]


def test_short_description_is_bounded_and_readable():
    text = "# " + ("A useful avatar sentence. " * 20)
    result = short_description(text, 80)
    assert len(result) <= 81
    assert result.startswith("A useful avatar sentence")


def test_run_reports_exact_missing_dimensions(tmp_path: Path):
    db = tmp_path / "catalog.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE collections (
            id TEXT PRIMARY KEY, name TEXT, tier TEXT,
            banner_image_url TEXT, description TEXT, curated_description TEXT,
            discord_url TEXT, twitter_username TEXT, image_url TEXT,
            sample_nft_image TEXT, release_date TEXT, vrm_url_https TEXT,
            vrm_url_pattern TEXT, avatar_count INTEGER, total_supply INTEGER,
            max_supply INTEGER, vrm_license TEXT, license_category TEXT,
            allowed_user TEXT, redistribution TEXT, vrm_check_status TEXT,
            vrm_check_url TEXT
        );
        CREATE TABLE avatars (
            id TEXT PRIMARY KEY, collection_id TEXT, model_file_url TEXT, is_public INTEGER
        );
        CREATE TABLE license_dimensions (
            collection_id TEXT PRIMARY KEY, color TEXT, confidence TEXT,
            use_scope TEXT, commercial_scope TEXT, credit TEXT,
            redistribute_original TEXT, modify TEXT, redistribute_modified TEXT,
            reason_codes TEXT
        );
        """
    )
    row = base_row(discord_url="")
    cols = list(row)
    conn.execute(
        f"INSERT INTO collections ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
        [row[c] for c in cols],
    )
    conn.executemany(
        "INSERT INTO avatars VALUES (?,?,?,?)",
        [
            ("1", "demo", "ipfs://bafy/1.vrm", 1),
            ("2", "demo", "ipfs://bafy/2.vrm", 1),
        ],
    )
    lf = complete_license_fact()
    conn.execute(
        """
        INSERT INTO license_dimensions
        (collection_id,color,confidence,use_scope,commercial_scope,redistribute_original)
        VALUES (?,?,?,?,?,?)
        """,
        ("demo", lf["color"], lf["confidence"], lf["use_scope"], lf["commercial_scope"], lf["redistribute_original"]),
    )
    conn.commit()
    conn.close()

    research = tmp_path / "research.json"
    research.write_text(
        json.dumps({"schema": "vrm-catalog-research-v1", "collections": {"demo": active_research()}}),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    report = run(db, research, output, {"A"})
    assert report["summary"]["collections"] == 1
    assert report["summary"]["complete"] == 0
    assert report["summary"]["missingByField"]["discord"] == 1
    assert report["summary"]["missingByField"]["x"] == 0
