#!/usr/bin/env python3
"""Binary-validate the catalog's existing staging source inventory.

This pass does not discover identities. It validates every concrete avatar URL
already present, records the same crawl evidence used by the recursive engine,
materializes valid avatar_vrm links, regenerates the Hubzz staging bundle, and
writes measured before/after reports.

The general crawler remains deliberately sequential. This bounded inventory pass
uses four workers because every task is an already-identified asset and the
catalog previously measured four workers as a safe ceiling for shared gateways.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.crawler.fetch import NetworkLoader  # noqa: E402
from scripts.crawler.models import (  # noqa: E402
    Binding,
    CrawlPolicy,
    PermanentCrawlError,
    RetryableCrawlError,
    RunSummary,
    VrmValidation,
)
from scripts.crawler.store import CrawlStore  # noqa: E402
from scripts.crawler.uri import canonicalize_uri  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def snapshot(conn: sqlite3.Connection) -> dict[str, int]:
    avatars = scalar(conn, "SELECT COUNT(*) FROM avatars") if table_exists(conn, "avatars") else 0
    reachable = scalar(
        conn,
        "SELECT COUNT(*) FROM avatars WHERE reachable=1 OR check_status IN ('ok_glb','ok_vrm')",
    ) if table_exists(conn, "avatars") else 0
    links = scalar(conn, "SELECT COUNT(*) FROM avatar_vrm") if table_exists(conn, "avatar_vrm") else 0
    validated_links = 0
    validated_sets = 0
    if table_exists(conn, "avatar_vrm") and table_exists(conn, "vrm_metadata"):
        validated_links = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM avatar_vrm av
            JOIN vrm_metadata vm ON vm.source_url=av.vrm_source_url
            WHERE vm.parse_error IS NULL AND vm.vrm_spec IS NOT NULL
            """,
        )
        validated_sets = scalar(
            conn,
            """
            SELECT COUNT(DISTINCT a.collection_id)
            FROM avatar_vrm av
            JOIN vrm_metadata vm ON vm.source_url=av.vrm_source_url
            JOIN avatars a ON a.id=av.avatar_id
            WHERE vm.parse_error IS NULL AND vm.vrm_spec IS NOT NULL
            """,
        )
    collection_validated = scalar(
        conn,
        "SELECT COUNT(*) FROM collections WHERE vrm_check_status='ok_vrm'",
    ) if table_exists(conn, "collections") else 0
    return {
        "avatars": avatars,
        "reachable_avatar_candidates": reachable,
        "avatar_vrm_links": links,
        "binary_validated_avatars": validated_links,
        "sets_with_binary_validated_avatars": validated_sets,
        "collections_with_validated_sample": collection_validated,
    }


def valid_hits(conn: sqlite3.Connection, run_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT b.collection_id, b.avatar_id, b.seed_source,
               t.kind, t.canonical_key, o.value_json, o.observed_at
        FROM crawl_observations o
        JOIN crawl_tasks t ON t.id=o.task_id
        JOIN crawl_bindings b ON b.task_id=t.id
        WHERE o.run_id=? AND o.predicate='valid_vrm'
        ORDER BY b.collection_id, b.avatar_id, t.id
        """,
        (run_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        value = json.loads(row["value_json"])
        key = (
            str(row["collection_id"] or ""),
            str(row["avatar_id"] or ""),
            str(value.get("canonical_url") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "collection_id": key[0],
                "avatar_id": key[1] or None,
                "seed_source": row["seed_source"],
                "task_kind": row["kind"],
                "canonical_url": value.get("canonical_url"),
                "transport_url": value.get("transport_url"),
                "vrm_spec": value.get("vrm_spec"),
                "total_length": value.get("total_length"),
                "observed_at": row["observed_at"],
            }
        )
    return out


def read_staging_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value.get("summary") or {}


def write_markdown(report: dict[str, Any], path: Path) -> None:
    before = report["before"]
    after = report["after"]
    delta = report["delta"]
    staging = report["staging_after"]
    lines = [
        "# Staging inventory binary-validation pass",
        "",
        f"Run at: `{report['finished_at']}`",
        "",
        "## Outcome",
        "",
        f"- Newly binary-validated avatars: **{delta['binary_validated_avatars']}**",
        f"- Sets gaining per-avatar binary proof: **{delta['sets_with_binary_validated_avatars']}**",
        f"- Binary-validated avatars after pass: **{after['binary_validated_avatars']} / {after['reachable_avatar_candidates']} reachable candidates**",
        f"- Stageable sets after pass: **{staging.get('stageableSets', 0)}**",
        f"- Deferred sets after pass: **{staging.get('deferredSets', 0)}**",
        "",
        "## Measurements",
        "",
        "| Metric | Before | After | Delta |",
        "|---|---:|---:|---:|",
    ]
    for key in before:
        lines.append(f"| `{key}` | {before[key]} | {after[key]} | {delta[key]} |")
    lines.extend(["", "## Validated hits", "", "| Set | Avatar | Spec | Bytes | Source |", "|---|---|---|---:|---|"])
    for hit in report["hits"]:
        lines.append(
            f"| `{hit['collection_id']}` | `{hit['avatar_id'] or ''}` | "
            f"{hit['vrm_spec'] or ''} | {hit['total_length'] or ''} | `{hit['canonical_url']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pending_avatar_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return concrete avatar URLs not already backed by parsed VRM metadata."""
    return conn.execute(
        """
        SELECT a.id, a.collection_id, a.model_file_url
        FROM avatars a
        WHERE a.model_file_url IS NOT NULL AND a.model_file_url!=''
          AND NOT EXISTS (
              SELECT 1
              FROM avatar_vrm av
              JOIN vrm_metadata vm ON vm.source_url=av.vrm_source_url
              WHERE av.avatar_id=a.id
                AND vm.parse_error IS NULL
                AND vm.vrm_spec IS NOT NULL
          )
        ORDER BY a.collection_id, a.id
        """
    ).fetchall()


def validate_with_retries(
    url: str,
    policy: CrawlPolicy,
    max_attempts: int,
) -> tuple[VrmValidation | None, dict[str, Any] | None, int]:
    """Validate one already-identified asset without sharing SQLite across threads."""
    loader = NetworkLoader(None, policy)  # validate_vrm does not access the store
    requests = 0
    last_error: dict[str, Any] | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = loader.validate_vrm(url)
            return replace(result, network_requests=requests + result.network_requests), None, requests + result.network_requests
        except RetryableCrawlError as exc:
            requests += exc.request_count
            last_error = {
                "class": exc.error_class,
                "message": str(exc),
                "retryable": True,
                "attempts": attempt,
            }
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 2))
        except PermanentCrawlError as exc:
            requests += exc.request_count
            return None, {
                "class": exc.error_class,
                "message": str(exc),
                "retryable": False,
                "attempts": attempt,
            }, requests
        except Exception as exc:  # defensive isolation for one URL
            return None, {
                "class": "internal_error",
                "message": f"{type(exc).__name__}: {exc}",
                "retryable": False,
                "attempts": attempt,
            }, requests
    return None, last_error or {
        "class": "validation_failed",
        "message": "validation failed without a classified error",
        "retryable": False,
        "attempts": max_attempts,
    }, requests


def run_parallel_avatar_validation(
    store: CrawlStore,
    policy: CrawlPolicy,
    *,
    workers: int,
    max_attempts: int,
) -> tuple[RunSummary, int, int]:
    """Validate unique asset URLs concurrently and write evidence serially."""
    rows = pending_avatar_rows(store.conn)
    run_id = store.create_run(
        policy,
        {
            "command": "run_staging_validation_pass.py",
            "mode": "bounded_parallel_assets",
            "workers": workers,
            "candidate_avatars": len(rows),
        },
    )
    tasks: dict[int, str] = {}
    for row in rows:
        try:
            canonical = canonicalize_uri(str(row["model_file_url"]))
        except PermanentCrawlError:
            continue
        task_id = store.enqueue(
            run_id,
            kind="asset",
            canonical_key=canonical,
            payload={"url": canonical},
            depth=0,
            priority=10,
            bindings=[
                Binding(
                    collection_id=str(row["collection_id"] or ""),
                    avatar_id=str(row["id"]),
                    seed_source="staging-inventory",
                )
            ],
        )
        tasks[task_id] = canonical
    store.add_root_seed(run_id, len(tasks))
    if not tasks:
        store.finish_run(run_id, "completed")
        return RunSummary(run_id=run_id, status="completed", requests_used=0), 0, 0

    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(validate_with_retries, url, policy, max_attempts): task_id
            for task_id, url in tasks.items()
        }
        for future in as_completed(futures):
            task_id = futures[future]
            validation, error, requests = future.result()
            store.increment_requests(run_id, requests)
            if validation is not None:
                predicate = "valid_vrm" if validation.valid else "asset_rejected"
                store.observe(
                    run_id,
                    task_id,
                    predicate,
                    asdict(validation),
                    source_url=validation.canonical_url,
                    confidence=1.0,
                    content_sha256=validation.content_sha256,
                )
                store.complete(task_id)
            else:
                assert error is not None
                store.observe(
                    run_id,
                    task_id,
                    "task_error",
                    error,
                    source_url=tasks[task_id],
                    confidence=1.0,
                )
                store.permanent_error(task_id, str(error.get("message") or "validation failed"))
            completed += 1
            if completed % 25 == 0 or completed == len(tasks):
                print(f"validated {completed}/{len(tasks)} unique asset URLs", file=sys.stderr)

    store.finish_run(run_id, "completed")
    materialized = store.materialize_valid_vrms(run_id)
    run = store.get_run(run_id)
    summary = RunSummary(
        run_id=run_id,
        status=str(run["status"]),
        requests_used=int(run["requests_used"]),
        task_counts=store.task_counts(run_id),
        observations=store.observation_count(run_id),
        materialized_collections=materialized,
    )
    return summary, materialized, len(tasks)


def main() -> int:
    parser = argparse.ArgumentParser(description="Binary-validate existing staging inventory")
    parser.add_argument("--db", default=str(_ROOT / "data" / "vrm_index.db"))
    parser.add_argument("--report", default=str(_ROOT / "data" / "staging_validation_report.json"))
    parser.add_argument("--markdown-report", default=str(_ROOT / "docs" / "staging-validation-latest.md"))
    parser.add_argument("--request-budget", type=int, default=1500)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"error: database not found: {db_path}", file=sys.stderr)
        return 2

    started = now()
    with CrawlStore(db_path) as store:
        store.ensure_schema()
        before = snapshot(store.conn)
        policy = CrawlPolicy(
            max_depth=0,
            request_budget=args.request_budget,
            max_tasks=20_000,
            max_attempts=args.max_attempts,
            timeout=args.timeout,
            max_document_bytes=2_000_000,
            max_vrm_json_bytes=4_000_000,
            max_links_per_document=0,
        )
        summary, materialized, seeded = run_parallel_avatar_validation(
            store,
            policy,
            workers=args.workers,
            max_attempts=args.max_attempts,
        )
        after = snapshot(store.conn)
        hits = valid_hits(store.conn, summary.run_id)

    staging_path = _ROOT / "static" / "data" / "hubzz-prealpha-staging.json"
    subprocess.run(
        [
            sys.executable,
            str(_ROOT / "scripts" / "export_hubzz_staging.py"),
            "--db",
            str(db_path),
            "--output",
            str(staging_path),
            "--report",
            str(_ROOT / "docs" / "hubzz-prealpha-staging.md"),
            "--validate",
        ],
        check=True,
    )
    if args.build:
        subprocess.run(
            [sys.executable, str(_ROOT / "scripts" / "build_catalog.py"), "--db", str(db_path)],
            check=True,
        )

    delta = {key: after[key] - before[key] for key in before}
    report = {
        "run_id": summary.run_id,
        "started_at": started,
        "finished_at": now(),
        "seeded_unique_asset_tasks": seeded,
        "workers": args.workers,
        "summary": {**asdict(summary), "materialized_collections": materialized},
        "before": before,
        "after": after,
        "delta": delta,
        "staging_after": read_staging_summary(staging_path),
        "hits": hits,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(report, Path(args.markdown_report))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if summary.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
