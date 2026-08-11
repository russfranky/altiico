"""Deterministic catalog snapshot identities shared by every exporter.

The snapshot digest is derived from durable SQLite state, not wall-clock time.
Transient HTTP caches and the snapshot ledger itself are excluded so repeated
exports from the same evidence state receive the same identifier.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

SNAPSHOT_PREFIX = "vrmcat-v1-"
MATERIALIZER_VERSION = "artifact-snapshot-1"

_EXCLUDED_TABLES = {
    "artifact_snapshots",
    "crawl_resources",
    "source_cache",
    "sqlite_sequence",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _normalise(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, float):
        # JSON's shortest round-trippable representation is stable on supported
        # Python versions; converting explicitly avoids locale influence.
        return float(repr(value))
    return value


def snapshot_tables(conn: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        if str(row[0]) not in _EXCLUDED_TABLES
    ]


def compute_db_digest(
    conn: sqlite3.Connection,
    *,
    tables: Iterable[str] | None = None,
) -> str:
    """Hash schema and rows in deterministic table/column order."""
    digest = hashlib.sha256()
    digest.update(b"vrm-catalog-artifact-snapshot-v1\0")

    selected = sorted(set(tables or snapshot_tables(conn)))
    for table in selected:
        schema_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if schema_row is None:
            continue
        table_info = conn.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
        columns = [str(row[1]) for row in table_info]
        if not columns:
            continue
        pk_columns = [
            str(row[1])
            for row in sorted(table_info, key=lambda item: int(item[5] or 0))
            if int(row[5] or 0) > 0
        ]
        order_columns = pk_columns or columns
        select_columns = ", ".join(_quote(name) for name in columns)
        order_clause = ", ".join(_quote(name) for name in order_columns)

        digest.update(table.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(schema_row[0] or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(json.dumps(columns, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\0")

        for row in conn.execute(
            f"SELECT {select_columns} FROM {_quote(table)} ORDER BY {order_clause}"
        ):
            values = [_normalise(value) for value in row]
            digest.update(
                json.dumps(
                    values,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
            digest.update(b"\n")

    return digest.hexdigest()


def compute_snapshot_id(conn: sqlite3.Connection) -> str:
    return SNAPSHOT_PREFIX + compute_db_digest(conn)[:24]


def ensure_snapshot_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS artifact_snapshots (
            snapshot_id          TEXT PRIMARY KEY,
            db_sha256            TEXT NOT NULL,
            materializer_version TEXT NOT NULL,
            source_cutoff_json   TEXT NOT NULL DEFAULT '{}',
            created_at           TEXT NOT NULL
        )
        """
    )


def record_snapshot(
    conn: sqlite3.Connection,
    *,
    materializer_version: str = MATERIALIZER_VERSION,
    source_cutoff: dict[str, Any] | None = None,
    commit: bool = True,
) -> str:
    """Record and return the deterministic snapshot for the current DB state."""
    ensure_snapshot_schema(conn)
    db_digest = compute_db_digest(conn)
    snapshot_id = SNAPSHOT_PREFIX + db_digest[:24]
    conn.execute(
        """
        INSERT INTO artifact_snapshots
            (snapshot_id, db_sha256, materializer_version, source_cutoff_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_id) DO NOTHING
        """,
        (
            snapshot_id,
            db_digest,
            materializer_version,
            json.dumps(source_cutoff or {}, sort_keys=True, separators=(",", ":")),
            utc_now(),
        ),
    )
    if commit:
        conn.commit()
    return snapshot_id


def snapshot_created_at(conn: sqlite3.Connection, snapshot_id: str) -> str:
    row = conn.execute(
        "SELECT created_at FROM artifact_snapshots WHERE snapshot_id=?",
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"snapshot was not recorded: {snapshot_id}")
    return str(row[0])
