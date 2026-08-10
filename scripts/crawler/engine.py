"""Persistent seed-driven recursive crawl engine."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterable

from scripts.crawler.fetch import EvmTokenResolver, NetworkLoader
from scripts.crawler.models import (
    Binding,
    CrawlPolicy,
    PermanentCrawlError,
    RetryableCrawlError,
    RunSummary,
    Task,
)
from scripts.crawler.store import CrawlStore
from scripts.crawler.uri import canonicalize_uri, discover_links


_TEMPLATE_RE = re.compile(r"\{(?:token_id|token|id)\}|%d", re.I)


class RecursiveCrawler:
    """Expand typed tasks until the frontier is empty or policy stops the run."""

    def __init__(
        self,
        store: CrawlStore,
        policy: CrawlPolicy,
        *,
        loader: NetworkLoader | None = None,
        evm_resolver: EvmTokenResolver | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.policy = policy
        self.loader = loader or NetworkLoader(store, policy)
        self.evm = evm_resolver or EvmTokenResolver(self.loader)
        self.sleeper = sleeper
        self.log = logger or (lambda _: None)

    # ------------------------------------------------------------------ seeds

    def new_run(self, config: dict[str, Any] | None = None) -> int:
        return self.store.create_run(self.policy, config)

    def seed_metadata(
        self,
        run_id: int,
        url: str,
        *,
        collection_id: str = "",
        avatar_id: str = "",
        source: str = "cli",
        priority: int = 20,
    ) -> int:
        canonical = canonicalize_uri(url)
        task_id = self.store.enqueue(
            run_id,
            kind="metadata",
            canonical_key=canonical,
            payload={"url": canonical},
            depth=0,
            priority=priority,
            bindings=[Binding(collection_id, avatar_id, source)],
        )
        self.store.add_root_seed(run_id)
        return task_id

    def seed_asset(
        self,
        run_id: int,
        url: str,
        *,
        collection_id: str = "",
        avatar_id: str = "",
        source: str = "cli",
        priority: int = 10,
    ) -> int:
        canonical = canonicalize_uri(url)
        task_id = self.store.enqueue(
            run_id,
            kind="asset",
            canonical_key=canonical,
            payload={"url": canonical},
            depth=0,
            priority=priority,
            bindings=[Binding(collection_id, avatar_id, source)],
        )
        self.store.add_root_seed(run_id)
        return task_id

    def seed_evm_token(
        self,
        run_id: int,
        chain: str,
        contract: str,
        token_id: int,
        *,
        collection_id: str = "",
        avatar_id: str = "",
        source: str = "cli",
        priority: int = 15,
    ) -> int:
        key = f"evm:{chain.lower()}:{contract.lower()}:{token_id}"
        task_id = self.store.enqueue(
            run_id,
            kind="evm_token",
            canonical_key=key,
            payload={
                "chain": chain.lower(),
                "contract": contract,
                "token_id": token_id,
            },
            depth=0,
            priority=priority,
            bindings=[Binding(collection_id, avatar_id, source)],
        )
        self.store.add_root_seed(run_id)
        return task_id

    def seed_existing_catalog(
        self,
        run_id: int,
        *,
        unresolved_only: bool = False,
        include_avatars: bool = False,
        collection_limit: int = 0,
        avatar_limit: int = 0,
    ) -> int:
        """Seed concrete URLs already held by canonical catalog records."""
        if not self._table_exists("collections"):
            return 0
        columns = self._columns("collections")
        wanted = ["id"]
        for name in (
            "sample_metadata_url",
            "vrm_url_https",
            "vrm_url_pattern",
            "vrm_check_status",
        ):
            if name in columns:
                wanted.append(name)
        sql = f"SELECT {', '.join(wanted)} FROM collections"
        if unresolved_only and "vrm_check_status" in columns:
            sql += " WHERE vrm_check_status IS NULL OR vrm_check_status!='ok_vrm'"
        sql += " ORDER BY id"
        if collection_limit:
            sql += f" LIMIT {int(collection_limit)}"
        seeded = 0
        for row in self.store.conn.execute(sql):
            cid = row["id"]
            metadata_url = row["sample_metadata_url"] if "sample_metadata_url" in row.keys() else None
            if metadata_url:
                try:
                    self.seed_metadata(
                        run_id,
                        metadata_url,
                        collection_id=cid,
                        source="existing:sample_metadata_url",
                    )
                    seeded += 1
                except PermanentCrawlError:
                    pass
            direct = row["vrm_url_https"] if "vrm_url_https" in row.keys() else None
            pattern = row["vrm_url_pattern"] if "vrm_url_pattern" in row.keys() else None
            candidate = direct or pattern
            if candidate and not _TEMPLATE_RE.search(candidate):
                try:
                    self.seed_asset(
                        run_id,
                        candidate,
                        collection_id=cid,
                        source="existing:vrm_url",
                    )
                    seeded += 1
                except PermanentCrawlError:
                    pass

        if include_avatars and self._table_exists("avatars"):
            avatar_columns = self._columns("avatars")
            if {"id", "collection_id", "model_file_url"} <= avatar_columns:
                sql = (
                    "SELECT id, collection_id, model_file_url FROM avatars "
                    "WHERE model_file_url IS NOT NULL AND model_file_url!='' "
                    "ORDER BY collection_id, id"
                )
                if avatar_limit:
                    sql += f" LIMIT {int(avatar_limit)}"
                for row in self.store.conn.execute(sql):
                    try:
                        self.seed_asset(
                            run_id,
                            row["model_file_url"],
                            collection_id=row["collection_id"] or "",
                            avatar_id=row["id"],
                            source="existing:avatar",
                        )
                        seeded += 1
                    except PermanentCrawlError:
                        pass
        return seeded

    def seed_records(self, run_id: int, records: Iterable[dict[str, Any]]) -> int:
        """Seed explicit JSON records without inferring identity from names."""
        count = 0
        for record in records:
            kind = record.get("kind")
            collection_id = str(record.get("collection_id") or "")
            avatar_id = str(record.get("avatar_id") or "")
            source = str(record.get("source") or "seed_file")
            if kind == "metadata":
                self.seed_metadata(
                    run_id,
                    str(record["url"]),
                    collection_id=collection_id,
                    avatar_id=avatar_id,
                    source=source,
                )
            elif kind == "asset":
                self.seed_asset(
                    run_id,
                    str(record["url"]),
                    collection_id=collection_id,
                    avatar_id=avatar_id,
                    source=source,
                )
            elif kind == "evm_token":
                self.seed_evm_token(
                    run_id,
                    str(record["chain"]),
                    str(record["contract"]),
                    int(record["token_id"]),
                    collection_id=collection_id,
                    avatar_id=avatar_id,
                    source=source,
                )
            else:
                raise ValueError(f"unsupported seed kind: {kind!r}")
            count += 1
        return count

    # -------------------------------------------------------------------- run

    def run(self, run_id: int, *, resume: bool = False) -> RunSummary:
        if resume:
            self.store.resume_run(run_id, request_budget=self.policy.request_budget)
        run = self.store.get_run(run_id)
        if run["status"] != "running":
            raise RuntimeError(f"crawl run {run_id} is {run['status']}, not running")
        self.store.recover_expired_leases(run_id)

        final_status = "completed"
        final_error = ""
        try:
            while True:
                run = self.store.get_run(run_id)
                if int(run["requests_used"]) >= int(run["request_budget"]):
                    final_status = "budget_exhausted"
                    break
                task = self.store.claim_next(run_id, self.policy.lease_seconds)
                if task is None:
                    break
                self.log(
                    f"[{task.id}] {task.kind} depth={task.depth} attempt={task.attempts} "
                    f"{task.canonical_key}"
                )
                self._process_task(task)
        except Exception as exc:  # pragma: no cover - defensive run-level guard
            final_status = "failed"
            final_error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if final_status == "completed" and self.store.pending_count(run_id):
                final_status = "budget_exhausted"
            self.store.finish_run(run_id, final_status, final_error)

        run = self.store.get_run(run_id)
        return RunSummary(
            run_id=run_id,
            status=run["status"],
            requests_used=int(run["requests_used"]),
            task_counts=self.store.task_counts(run_id),
            observations=self.store.observation_count(run_id),
        )

    def _process_task(self, task: Task) -> None:
        try:
            if task.depth > self.policy.max_depth:
                self.store.reject(task.id, "maximum recursion depth exceeded")
                return
            if task.kind == "metadata":
                self._process_metadata(task)
            elif task.kind == "asset":
                self._process_asset(task)
            elif task.kind == "evm_token":
                self._process_evm_token(task)
            else:
                self.store.permanent_error(task.id, f"unknown task kind: {task.kind}")
        except RetryableCrawlError as exc:
            self.store.increment_requests(task.run_id, exc.request_count)
            self.store.observe(
                task.run_id,
                task.id,
                "task_error",
                {"class": exc.error_class, "message": str(exc), "retryable": True},
                confidence=1.0,
            )
            if task.attempts >= self.policy.max_attempts:
                self.store.permanent_error(task.id, str(exc))
                return
            delay = exc.retry_after if exc.retry_after is not None else min(2**task.attempts, 8)
            delay = max(0.0, min(float(delay), 30.0))
            if delay:
                self.sleeper(delay)
            self.store.retry(task.id, str(exc), delay_seconds=0)
        except PermanentCrawlError as exc:
            self.store.increment_requests(task.run_id, exc.request_count)
            self.store.observe(
                task.run_id,
                task.id,
                "task_error",
                {"class": exc.error_class, "message": str(exc), "retryable": False},
                confidence=1.0,
            )
            self.store.permanent_error(task.id, str(exc))
        except Exception as exc:  # task isolation is deliberate
            self.store.observe(
                task.run_id,
                task.id,
                "task_error",
                {
                    "class": "internal_error",
                    "message": f"{type(exc).__name__}: {exc}",
                    "retryable": False,
                },
                confidence=1.0,
            )
            self.store.permanent_error(task.id, f"{type(exc).__name__}: {exc}")

    def _process_metadata(self, task: Task) -> None:
        url = task.payload["url"]
        document, result, digest = self.loader.load_json(url)
        self.store.increment_requests(task.run_id, result.network_requests)
        self.store.observe(
            task.run_id,
            task.id,
            "metadata_loaded",
            {
                "canonical_url": result.canonical_url,
                "transport_url": result.final_url,
                "content_type": result.content_type,
                "from_cache": result.from_cache,
            },
            source_url=result.canonical_url,
            confidence=1.0,
            content_sha256=digest,
        )

        links = discover_links(
            document,
            result.canonical_url,
            max_links=self.policy.max_links_per_document,
        )
        bindings = self.store.bindings_for_task(task.id)
        for link in links:
            self.store.observe(
                task.run_id,
                task.id,
                link.relation,
                {"kind": link.kind, "url": link.url, "reason": link.reason},
                source_url=result.canonical_url,
                json_path=link.path,
                confidence=link.confidence,
                content_sha256=digest,
            )
            if task.depth + 1 > self.policy.max_depth:
                continue
            if self.store.task_count(task.run_id) >= self.policy.max_tasks:
                self.store.observe(
                    task.run_id,
                    task.id,
                    "expansion_skipped",
                    {"reason": "max_tasks", "url": link.url},
                    json_path=link.path,
                    confidence=1.0,
                )
                continue
            self.store.enqueue(
                task.run_id,
                kind=link.kind,
                canonical_key=link.url,
                payload={"url": link.url},
                depth=task.depth + 1,
                priority=30 if link.kind == "asset" else 50,
                bindings=bindings,
                parent_task_id=task.id,
                relation=link.relation,
                json_path=link.path,
                reason=link.reason,
                confidence=link.confidence,
            )
        self.store.complete(task.id)

    def _process_asset(self, task: Task) -> None:
        validation = self.loader.validate_vrm(task.payload["url"])
        self.store.increment_requests(task.run_id, validation.network_requests)
        predicate = "valid_vrm" if validation.valid else "asset_rejected"
        self.store.observe(
            task.run_id,
            task.id,
            predicate,
            asdict(validation),
            source_url=validation.canonical_url,
            confidence=1.0,
            content_sha256=validation.content_sha256,
        )
        self.store.complete(task.id)

    def _process_evm_token(self, task: Task) -> None:
        payload = task.payload
        uri, requests, standard = self.evm.resolve(
            payload["chain"], payload["contract"], int(payload["token_id"])
        )
        self.store.increment_requests(task.run_id, requests)
        self.store.observe(
            task.run_id,
            task.id,
            "token_metadata_uri",
            {
                "chain": payload["chain"],
                "contract": payload["contract"],
                "token_id": int(payload["token_id"]),
                "token_standard": standard,
                "uri": uri,
            },
            source_url=uri,
            confidence=1.0,
        )
        if task.depth + 1 <= self.policy.max_depth:
            self.store.enqueue(
                task.run_id,
                kind="metadata",
                canonical_key=uri,
                payload={"url": uri},
                depth=task.depth + 1,
                priority=20,
                bindings=self.store.bindings_for_task(task.id),
                parent_task_id=task.id,
                relation="token_has_metadata",
                reason=standard,
                confidence=1.0,
            )
        self.store.complete(task.id)

    # -------------------------------------------------------------- utilities

    def materialize(self, run_id: int) -> int:
        return self.store.materialize_valid_vrms(run_id)

    def _table_exists(self, table: str) -> bool:
        return (
            self.store.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            is not None
        )

    def _columns(self, table: str) -> set[str]:
        return {row[1] for row in self.store.conn.execute(f"PRAGMA table_info({table})")}


def load_seed_file(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSON array or newline-delimited JSON seed file."""
    raw = Path(path).read_text(encoding="utf-8")
    stripped = raw.lstrip()
    if stripped.startswith("["):
        value = json.loads(raw)
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ValueError("seed JSON must be an array of objects")
        return value
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"seed line {line_no} is not an object")
        records.append(item)
    return records
