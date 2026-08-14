import sqlite3
from pathlib import Path

from scripts.materialize_short_descriptions import run, short_description


def test_short_description_is_bounded_and_prefers_sentence_boundary():
    text = "Useful first sentence. " + ("More detail " * 40)
    result = short_description(text, max_chars=80)
    assert result == "Useful first sentence."


def test_materializer_preserves_manual_short_description_and_fills_blanks(tmp_path: Path):
    db = tmp_path / "catalog.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE collections (
          id TEXT PRIMARY KEY,
          short_description TEXT,
          curated_description TEXT,
          description TEXT
        );
        INSERT INTO collections VALUES ('manual','Manual summary','Curated long','Long');
        INSERT INTO collections VALUES ('derived',NULL,NULL,'A useful collection description with enough detail for a card.');
        INSERT INTO collections VALUES ('missing',NULL,NULL,NULL);
        """
    )
    conn.commit(); conn.close()

    result = run(db)
    assert result == {
        "collections": 3,
        "updated": 1,
        "alreadyPresent": 1,
        "missingSourceDescription": 1,
    }

    conn = sqlite3.connect(db)
    rows = dict(conn.execute("SELECT id,short_description FROM collections"))
    conn.close()
    assert rows["manual"] == "Manual summary"
    assert rows["derived"].startswith("A useful collection description")
    assert rows["missing"] is None
