"""SQLite-backed frontier, evidence graph, cache, and materializer."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from scripts.crawler.models import Binding, CrawlPolicy, Task


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION = _REPO_ROOT / "migrations" / "022_recursive_crawler.sql"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_after(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class CrawlStore:
    """Owns all crawler writes and keeps canonical catalog writes transactional."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "CrawlStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def ensure_schema(self, migration_path: Path = _MIGRATION) -> None:
        if not migration_path.exists():
            raise FileNotFoundError(f"crawler migration not found: {migration_path}")
        self.conn.executescript(migration_path.read_text(encoding="utf-8"))
        self.conn.commit()

    # ------------------------------------------------------------------ runs

    def create_run(self, policy: CrawlPolicy, config: dict[str, Any] | None = None) -> int:
        merged = {"policy": policy.as_dict(), **(config or {})}
        cur = self.conn.execute(
            """
            INSERT INTO crawl_runs
                (started_at, status, config_json, request_budget, requests_used,
                 root_seed_count)
            VALUES (?, 'running', ?, ?, 0, 0)
            """,
            (utc_now(), _json(merged), policy.request_budget),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def resume_run(self, run_id: int, request_budget: int | None = None) -> None:
        self.get_run(run_id)
        if request_budget is None:
            self.conn.execute(
                "UPDATE crawl_runs SET status='running', finished_at=NULL, last_error=NULL WHERE id=?",
                (run_id,),
            )
        else:
            self.conn.execute(
                """
                UPDATE crawl_runs
                SET status='running', finished_at=NULL, last_error=NULL,
                    request_budget=?
                WHERE id=?
                """,
                (request_budget, run_id),
            )
        self.conn.commit()

    def get_run(self, run_id: int) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM crawl_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"crawl run {run_id} does not exist")
        return row

    def add_root_seed(self, run_id: int, count: int = 1) -> None:
        self.conn.execute(
            "UPDATE crawl_runs SET root_seed_count=root_seed_count+? WHERE id=?",
            (count, run_id),
        )
        self.conn.commit()

    def increment_requests(self, run_id: int, count: int) -> None:
        if count <= 0:
            return
        self.conn.execute(
            "UPDATE crawl_runs SET requests_used=requests_used+? WHERE id=?",
            (count, run_id),
        )
        self.conn.commit()

    def finish_run(self, run_id: int, status: str, error: str = "") -> None:
        self.conn.execute(
            """
            UPDATE crawl_runs
            SET status=?, finished_at=?, last_error=?
            WHERE id=?
            """,
            (status, utc_now(), error[:2000] if error else None, run_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ tasks

    def task_count(self, run_id: int) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM crawl_tasks WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        )

    def enqueue(
        self,
        run_id: int,
        *,
        kind: str,
        canonical_key: str,
        payload: dict[str, Any],
        depth: int,
        priority: int = 100,
        bindings: Iterable[Binding] = (),
        parent_task_id: int | None = None,
        relation: str = "",
        json_path: str = "",
        reason: str = "",
        confidence: float = 0.5,
    ) -> int:
        now = utc_now()
        with self.transaction():
            self.conn.execute(
                """
                INSERT INTO crawl_tasks
                    (run_id, kind, canonical_key, payload_json, depth, priority,
                     state, attempts, available_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?)
                ON CONFLICT(run_id, kind, canonical_key) DO UPDATE SET
                    priority=MIN(crawl_tasks.priority, excluded.priority),
                    depth=MIN(crawl_tasks.depth, excluded.depth)
                """,
                (
                    run_id,
                    kind,
                    canonical_key,
                    _json(payload),
                    depth,
                    priority,
                    now,
                    now,
                ),
            )
            row = self.conn.execute(
                """
                SELECT id FROM crawl_tasks
                WHERE run_id=? AND kind=? AND canonical_key=?
                """,
                (run_id, kind, canonical_key),
            ).fetchone()
            assert row is not None
            task_id = int(row["id"])

            for binding in bindings:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO crawl_bindings
                        (task_id, collection_id, avatar_id, seed_source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        binding.collection_id or "",
                        binding.avatar_id or "",
                        binding.seed_source or "",
                    ),
                )

            if parent_task_id is not None:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO crawl_edges
                        (run_id, parent_task_id, child_task_id, relation,
                         json_path, reason, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        parent_task_id,
                        task_id,
                        relation or "discovered",
                        json_path or "",
                        reason or "",
                        confidence,
                        now,
                    ),
                )
        return task_id

    def bindings_for_task(self, task_id: int) -> list[Binding]:
        return [
            Binding(
                collection_id=row["collection_id"],
                avatar_id=row["avatar_id"],
                seed_source=row["seed_source"],
            )
            for row in self.conn.execute(
                """
                SELECT collection_id, avatar_id, seed_source
                FROM crawl_bindings WHERE task_id=?
                ORDER BY collection_id, avatar_id, seed_source
                """,
                (task_id,),
            )
        ]

    def recover_expired_leases(self, run_id: int) -> int:
        cur = self.conn.execute(
            """
            UPDATE crawl_tasks
            SET state='queued', lease_until=NULL,
                last_error=COALESCE(last_error, 'lease expired')
            WHERE run_id=? AND state='leased'
              AND lease_until IS NOT NULL AND lease_until <= ?
            """,
            (run_id, utc_now()),
        )
        self.conn.commit()
        return cur.rowcount

    def claim_next(self, run_id: int, lease_seconds: int) -> Task | None:
        now = utc_now()
        with self.transaction():
            row = self.conn.execute(
                """
                SELECT * FROM crawl_tasks
                WHERE run_id=?
                  AND state IN ('queued', 'retry')
                  AND (available_at IS NULL OR available_at <= ?)
                ORDER BY priority ASC, depth ASC, id ASC
                LIMIT 1
                """,
                (run_id, now),
            ).fetchone()
            if row is None:
                return None
            self.conn.execute(
                """
                UPDATE crawl_tasks
                SET state='leased', attempts=attempts+1,
                    lease_until=?, last_error=NULL
                WHERE id=?
                """,
                (utc_after(lease_seconds), row["id"]),
            )
            attempts = int(row["attempts"]) + 1
        return Task(
            id=int(row["id"]),
            run_id=int(row["run_id"]),
            kind=row["kind"],
            canonical_key=row["canonical_key"],
            payload=json.loads(row["payload_json"]),
            depth=int(row["depth"]),
            priority=int(row["priority"]),
            state="leased",
            attempts=attempts,
        )

    def complete(self, task_id: int) -> None:
        self.conn.execute(
            """
            UPDATE crawl_tasks
            SET state='done', completed_at=?, lease_until=NULL
            WHERE id=?
            """,
            (utc_now(), task_id),
        )
        self.conn.commit()

    def reject(self, task_id: int, message: str) -> None:
        self.conn.execute(
            """
            UPDATE crawl_tasks
            SET state='rejected', completed_at=?, lease_until=NULL, last_error=?
            WHERE id=?
            """,
            (utc_now(), message[:2000], task_id),
        )
        self.conn.commit()

    def permanent_error(self, task_id: int, message: str) -> None:
        self.conn.execute(
            """
            UPDATE crawl_tasks
            SET state='permanent_error', completed_at=?, lease_until=NULL,
                last_error=?
            WHERE id=?
            """,
            (utc_now(), message[:2000], task_id),
        )
        self.conn.commit()

    def retry(self, task_id: int, message: str, delay_seconds: float = 0) -> None:
        self.conn.execute(
            """
            UPDATE crawl_tasks
            SET state='retry', available_at=?, lease_until=NULL, last_error=?
            WHERE id=?
            """,
            (utc_after(delay_seconds), message[:2000], task_id),
        )
        self.conn.commit()

    def pending_count(self, run_id: int) -> int:
        return int(
            self.conn.execute(
                """
                SELECT COUNT(*) FROM crawl_tasks
                WHERE run_id=? AND state IN ('queued', 'retry', 'leased')
                """,
                (run_id,),
            ).fetchone()[0]
        )

    # ------------------------------------------------------------- observations

    def observe(
        self,
        run_id: int,
        task_id: int,
        predicate: str,
        value: Any,
        *,
        source_url: str = "",
        json_path: str = "",
        confidence: float = 0.5,
        content_sha256: str = "",
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO crawl_observations
                (run_id, task_id, predicate, value_json, source_url, json_path,
                 confidence, content_sha256, observed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                task_id,
                predicate,
                _json(value),
                source_url or "",
                json_path or "",
                confidence,
                content_sha256 or "",
                utc_now(),
            ),
        )
        self.conn.commit()

    # ---------------------------------------------------------------- resources

    def get_resource(self, canonical_url: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM crawl_resources WHERE canonical_url=?",
            (canonical_url,),
        ).fetchone()

    def put_resource(
        self,
        canonical_url: str,
        *,
        final_url: str,
        status: str,
        http_status: int | None,
        content_type: str,
        body_sha256: str,
        body_text: str | None,
        etag: str = "",
        last_modified: str = "",
        expires_at: str,
        error_class: str = "",
        error_message: str = "",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO crawl_resources
                (canonical_url, final_url, status, http_status, content_type,
                 body_sha256, body_text, etag, last_modified, fetched_at,
                 expires_at, error_class, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_url) DO UPDATE SET
                final_url=excluded.final_url,
                status=excluded.status,
                http_status=excluded.http_status,
                content_type=excluded.content_type,
                body_sha256=excluded.body_sha256,
                body_text=excluded.body_text,
                etag=excluded.etag,
                last_modified=excluded.last_modified,
                fetched_at=excluded.fetched_at,
                expires_at=excluded.expires_at,
                error_class=excluded.error_class,
                error_message=excluded.error_message
            """,
            (
                canonical_url,
                final_url,
                status,
                http_status,
                content_type,
                body_sha256,
                body_text,
                etag,
                last_modified,
                utc_now(),
                expires_at,
                error_class,
                error_message[:2000],
            ),
        )
        self.conn.commit()

    # --------------------------------------------------------------- reporting

    def task_counts(self, run_id: int) -> dict[str, int]:
        return {
            row["state"]: int(row["n"])
            for row in self.conn.execute(
                """
                SELECT state, COUNT(*) AS n
                FROM crawl_tasks WHERE run_id=? GROUP BY state
                """,
                (run_id,),
            )
        }

    def observation_count(self, run_id: int) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM crawl_observations WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
        )

    def explain_collection(self, run_id: int, collection_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT t.id AS task_id, t.kind, t.canonical_key, t.state,
                   o.predicate, o.value_json, o.source_url, o.json_path,
                   o.confidence, o.observed_at
            FROM crawl_bindings b
            JOIN crawl_tasks t ON t.id=b.task_id
            LEFT JOIN crawl_observations o ON o.task_id=t.id
            WHERE t.run_id=? AND b.collection_id=?
            ORDER BY t.depth, t.id, o.id
            """,
            (run_id, collection_id),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if item.get("value_json"):
                item["value"] = json.loads(item.pop("value_json"))
            else:
                item.pop("value_json", None)
            out.append(item)
        return out

    # -------------------------------------------------------------- materialize

    def _table_exists(self, table: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            is not None
        )

    def _columns(self, table: str) -> set[str]:
        return {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}

    def materialize_valid_vrms(self, run_id: int) -> int:
        """Apply validated assets to already-identified catalog records.

        This deliberately never invents a collection identity. A task must carry
        an explicit collection binding, and that collection must already exist.
        """
        if not self._table_exists("collections"):
            return 0
        collection_columns = self._columns("collections")
        avatar_columns = self._columns("avatars") if self._table_exists("avatars") else set()
        has_vrm_metadata = self._table_exists("vrm_metadata")
        has_avatar_vrm = self._table_exists("avatar_vrm")
        vrm_metadata_columns = self._columns("vrm_metadata") if has_vrm_metadata else set()

        rows = self.conn.execute(
            """
            SELECT DISTINCT
                b.collection_id, b.avatar_id, t.id AS task_id,
                o.value_json
            FROM crawl_observations o
            JOIN crawl_tasks t ON t.id=o.task_id
            JOIN crawl_bindings b ON b.task_id=t.id
            WHERE o.run_id=? AND o.predicate='valid_vrm'
              AND b.collection_id!=''
            ORDER BY b.collection_id, b.avatar_id, t.id
            """,
            (run_id,),
        ).fetchall()
        if not rows:
            return 0

        materialized: set[str] = set()
        collection_selected: set[str] = set()
        stamp = utc_now()
        with self.transaction():
            for row in rows:
                collection_id = row["collection_id"]
                exists = self.conn.execute(
                    "SELECT * FROM collections WHERE id=?", (collection_id,)
                ).fetchone()
                if exists is None:
                    continue
                validation = json.loads(row["value_json"])
                canonical_url = validation["canonical_url"]
                transport_url = validation["transport_url"]

                updates: dict[str, Any] = {}
                first_for_collection = collection_id not in collection_selected
                collection_selected.add(collection_id)
                existing_url = (
                    exists["vrm_url_https"] if "vrm_url_https" in collection_columns else None
                )
                already_confirmed = (
                    "vrm_check_status" in collection_columns
                    and exists["vrm_check_status"] == "ok_vrm"
                    and bool(existing_url)
                )
                # Never replace a different already-confirmed collection URL.
                # The new asset remains in evidence and vrm_metadata, but a human
                # must resolve which valid asset represents the collection row.
                may_update_collection = first_for_collection and (
                    not already_confirmed or existing_url == transport_url
                )
                if may_update_collection:
                    if "vrm_url_https" in collection_columns:
                        updates["vrm_url_https"] = transport_url
                    if "vrm_reachable" in collection_columns:
                        updates["vrm_reachable"] = 1
                    if "vrm_check_status" in collection_columns:
                        updates["vrm_check_status"] = "ok_vrm"
                    if "vrm_check_bytes" in collection_columns:
                        updates["vrm_check_bytes"] = (
                            validation.get("observed_length")
                            or validation.get("total_length")
                        )
                    if "vrm_check_url" in collection_columns:
                        updates["vrm_check_url"] = transport_url
                    if "vrm_checked_at" in collection_columns:
                        updates["vrm_checked_at"] = stamp

                for field, new_value in updates.items():
                    old_value = exists[field]
                    if old_value == new_value:
                        continue
                    self.conn.execute(
                        f"UPDATE collections SET {field}=? WHERE id=?",
                        (new_value, collection_id),
                    )
                    self.conn.execute(
                        """
                        INSERT INTO crawl_materializations
                            (run_id, collection_id, avatar_id, field_name,
                             old_value, new_value, materialized_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(run_id, collection_id, avatar_id, field_name)
                        DO UPDATE SET
                            old_value=excluded.old_value,
                            new_value=excluded.new_value,
                            materialized_at=excluded.materialized_at
                        """,
                        (
                            run_id,
                            collection_id,
                            row["avatar_id"],
                            field,
                            None if old_value is None else str(old_value),
                            None if new_value is None else str(new_value),
                            stamp,
                        ),
                    )

                if has_vrm_metadata:
                    metadata_values: dict[str, Any] = {
                        "source_url": canonical_url,
                        "extracted_at": stamp,
                        "extractor_version": validation.get("extractor_version") or "recursive-crawler-2",
                        "vrm_spec": validation.get("vrm_spec"),
                        "vrm_meta_json": _json(validation.get("raw_meta")),
                        "parse_error": None,
                        "content_length": validation.get("observed_length") or validation.get("total_length"),
                        "content_sha256": validation.get("content_sha256") or None,
                        "json_chunk_sha256": validation.get("json_chunk_sha256") or None,
                        "observed_content_length": validation.get("observed_length"),
                        "transport_url": transport_url,
                    }
                    write_values = {
                        name: value
                        for name, value in metadata_values.items()
                        if name in vrm_metadata_columns
                    }
                    names = list(write_values)
                    update_names = [name for name in names if name != "source_url"]
                    placeholders = ", ".join("?" for _ in names)
                    update_clause = ", ".join(
                        f"{name}=excluded.{name}" for name in update_names
                    )
                    self.conn.execute(
                        f"INSERT INTO vrm_metadata ({', '.join(names)}) "
                        f"VALUES ({placeholders}) "
                        f"ON CONFLICT(source_url) DO UPDATE SET {update_clause}",
                        tuple(write_values[name] for name in names),
                    )

                avatar_id = row["avatar_id"]
                if avatar_id and avatar_columns:
                    avatar_exists = self.conn.execute(
                        "SELECT 1 FROM avatars WHERE id=?", (avatar_id,)
                    ).fetchone()
                    if avatar_exists:
                        avatar_updates: dict[str, Any] = {}
                        if "reachable" in avatar_columns:
                            avatar_updates["reachable"] = 1
                        if "check_status" in avatar_columns:
                            avatar_updates["check_status"] = "ok_vrm"
                        if "checked_at" in avatar_columns:
                            avatar_updates["checked_at"] = stamp
                        if "model_file_url" in avatar_columns:
                            avatar_updates["model_file_url"] = transport_url
                        if avatar_updates:
                            clause = ", ".join(f"{name}=?" for name in avatar_updates)
                            self.conn.execute(
                                f"UPDATE avatars SET {clause} WHERE id=?",
                                (*avatar_updates.values(), avatar_id),
                            )
                        if has_avatar_vrm:
                            self.conn.execute(
                                """
                                INSERT INTO avatar_vrm (avatar_id, vrm_source_url)
                                VALUES (?, ?)
                                ON CONFLICT(avatar_id) DO UPDATE SET
                                    vrm_source_url=excluded.vrm_source_url
                                """,
                                (avatar_id, canonical_url),
                            )
                materialized.add(collection_id)

            integrity = self.conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"SQLite integrity check failed: {integrity}")

        return len(materialized)
