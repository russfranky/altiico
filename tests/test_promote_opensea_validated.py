import json
import sqlite3

from scripts.promote_opensea_validated import (
    collection_title,
    is_admissible,
    is_named_slug,
    promote,
    stored_contract,
)


def _vrm(sha: str, token_id: str, bytes_: int = 1000) -> dict:
    return {
        "canonical_url": f"https://example.test/{sha}.glb",
        "transport_url": f"https://example.test/{sha}.glb",
        "valid": True,
        "status": "valid_vrm",
        "vrm_spec": "0.x",
        "content_sha256": sha,
        "bytes": bytes_,
        "token_id": token_id,
        "field": "animation_url",
    }


def _nft(slug: str, token_id: str, sha: str, name: str, contract: str, chain: str = "polygon") -> dict:
    return {
        "collection": slug,
        "name": name,
        "chain": chain,
        "contract": contract,
        "token_id": token_id,
        "validated_vrms": [_vrm(sha, token_id), _vrm(sha, token_id)],  # CDN mirror
        "search_payload": {"image_url": "https://example.test/img.png"},
    }


def test_untitled_and_junk_slugs_are_not_named():
    assert not is_named_slug("untitled-collection-195722659")
    assert not is_named_slug("ens")
    assert is_named_slug("cyber-across-verse")


def test_title_strips_token_number_and_vrm_suffix():
    assert (
        collection_title(
            [
                "Cyber Across Verse #024 3D Avatar Character .vrm",
                "Cyber Across Verse #003 3D Avatar Character .vrm",
            ],
            "cyber-across-verse",
        )
        == "Cyber Across Verse"
    )


def test_shared_storefront_contract_is_not_stored():
    assert (
        stored_contract({"contract": "0x2953399124f0cbb46d2cbacd8a89cf0599974963"})
        == ""
    )
    assert (
        stored_contract({"contract": "0xefb95e27cdb5055ed5967b7a2c19f32d47a56de3"})
        == "0xefb95e27cdb5055ed5967b7a2c19f32d47a56de3"
    )


def test_admission_requires_three_unique_token_vrms():
    rec = {
        "validations": [_vrm("a", "1"), _vrm("b", "2")],
        "token_ids": ["1", "2"],
    }
    assert not is_admissible(rec)
    rec["validations"].append(_vrm("c", "3"))
    rec["token_ids"].append("3")
    assert is_admissible(rec)


def test_promote_admits_named_series_and_skips_untitled_and_singletons(tmp_path):
    polygon_shared = "0x2953399124f0cbb46d2cbacd8a89cf0599974963"
    report = {
        "generated_at": "2026-08-16T22:32:04Z",
        "nfts": [
            _nft("cyber-across-verse", "1", "aa" * 32, "Cyber Across Verse #001 3D Avatar Character .vrm", polygon_shared),
            _nft("cyber-across-verse", "2", "bb" * 32, "Cyber Across Verse #002 3D Avatar Character .vrm", polygon_shared),
            _nft("cyber-across-verse", "3", "cc" * 32, "Cyber Across Verse #003 3D Avatar Character .vrm", polygon_shared),
            _nft("untitled-collection-9", "9", "dd" * 32, "NFT Avatar (VRM)", polygon_shared),
            _nft(
                "art-unchained-editions",
                "1",
                "ee" * 32,
                "LIT Rat 3D VRM Avatar",
                "0xefb95e27cdb5055ed5967b7a2c19f32d47a56de3",
                "ethereum",
            ),
        ],
    }
    db = tmp_path / "vrm.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT, tier TEXT, chain TEXT, contract TEXT, opensea_slug TEXT, vrm_param TEXT, vrm_url_pattern TEXT, license_category TEXT, vrm_license TEXT, commercial_use TEXT, allowed_user TEXT, redistribution TEXT, creator TEXT, description TEXT, notes TEXT, source TEXT, image_url TEXT, banner_image_url TEXT, project_url TEXT)"
    )
    conn.execute(
        "CREATE TABLE contracts (collection_id TEXT, address TEXT, chain TEXT, token_standard TEXT, is_primary INTEGER)"
    )
    conn.execute(
        """CREATE TABLE promotion_candidates (
            candidate_id TEXT PRIMARY KEY, collection_id TEXT, chain TEXT, contract TEXT, token_id TEXT,
            name TEXT, model_url TEXT, canonical_url TEXT, source TEXT, observed_at TEXT,
            validation_status TEXT, vrm_spec TEXT, sha256 TEXT, byte_length INTEGER,
            promotion_state TEXT, reason TEXT, evidence_json TEXT
        )"""
    )
    summary = promote(report, conn)
    conn.commit()
    rows = list(conn.execute("SELECT id, name, contract, vrm_check_status, source FROM collections"))
    conn.close()
    assert [row[0] for row in rows] == ["cyber-across-verse"]
    assert rows[0][1] == "Cyber Across Verse"
    assert rows[0][2] == ""
    assert rows[0][3] == "ok_vrm"
    assert rows[0][4] == "opensea-nft-discovery"
    skipped = {item["slug"] for item in summary["skipped"]}
    assert "art-unchained-editions" in skipped
    assert [item["id"] for item in summary["admitted"]] == ["cyber-across-verse"]
    assert summary["admitted"][0]["uniqueValidatedVrms"] == 3
