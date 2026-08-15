import json
import sqlite3
from pathlib import Path

from scripts.materialize_public_vrm_access import run


def make_db(path: Path, mode=None):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE collections (
          id TEXT PRIMARY KEY,
          file_access_mode TEXT,
          file_access_requires_ownership INTEGER
        );
        """
    )
    conn.execute(
        "INSERT INTO collections VALUES ('demo',?,NULL)",
        (mode,),
    )
    conn.commit(); conn.close()


def write_reports(tmp_path: Path, *, structurally_complete=True):
    inventory = tmp_path / "inventory.json"
    probe = tmp_path / "probe.json"
    inventory.write_text(
        json.dumps(
            {
                "collections": [
                    {
                        "collection_id": "demo",
                        "state": "complete",
                        "complete": True,
                        "urls": ["https://cdn.test/1.vrm", "https://cdn.test/2.vrm"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    probe.write_text(
        json.dumps(
            {
                "collections": [
                    {
                        "catalogId": "demo",
                        "structurallyComplete": structurally_complete,
                        "validVrmUrls": 2 if structurally_complete else 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return inventory, probe


def test_successful_unauthenticated_full_probe_materializes_public_access(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    inventory, probe = write_reports(tmp_path)

    result = run(db, inventory, probe)
    assert result["updatedPublic"] == 1

    conn = sqlite3.connect(db)
    access = conn.execute(
        "SELECT file_access_mode,file_access_requires_ownership FROM collections WHERE id='demo'"
    ).fetchone()
    evidence = conn.execute(
        "SELECT state,value_json FROM catalog_research_evidence WHERE collection_id='demo' AND field='file_access'"
    ).fetchone()
    conn.close()
    assert access == ("public", 0)
    assert evidence[0] == "public"
    assert json.loads(evidence[1])["requires_ownership"] is False


def test_partial_or_invalid_probe_does_not_infer_public_access(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db)
    inventory, probe = write_reports(tmp_path, structurally_complete=False)
    result = run(db, inventory, probe)
    assert result["updatedPublic"] == 0
    assert result["notProvenPublic"] == 1


def test_explicit_holder_gating_is_never_overwritten(tmp_path: Path):
    db = tmp_path / "catalog.db"
    make_db(db, mode="holder_gated")
    inventory, probe = write_reports(tmp_path)
    result = run(db, inventory, probe)
    assert result["updatedPublic"] == 0
    assert result["alreadyResolved"] == 1
    conn = sqlite3.connect(db)
    mode = conn.execute("SELECT file_access_mode FROM collections WHERE id='demo'").fetchone()[0]
    conn.close()
    assert mode == "holder_gated"
