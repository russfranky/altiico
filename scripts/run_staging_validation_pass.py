#!/usr/bin/env python3
"""Binary-validate the catalog's existing staging source inventory.

This pass does not discover identities. It seeds every concrete collection and
avatar URL already present, runs the recursive crawler's GLB/VRM validator,
materializes valid avatar_vrm links, regenerates the Hubzz staging bundle, and
writes measured before/after reports.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.crawler.engine import RecursiveCrawler  # noqa: E402
from scripts.crawler.models import CrawlPolicy  # noqa: E402
from scripts.crawler.store import CrawlStore  # noqa: E402


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Binary-validate existing staging inventory")
    parser.add_argument("--db", default=str(_ROOT / "data" / "vrm_index.db"))
    parser.add_argument("--report", default=str(_ROOT / "data" / "staging_validation_report.json"))
    parser.add_argument("--markdown-report", default=str(_ROOT / "docs" / "staging-validation-latest.md"))
    parser.add_argument("--request-budget", type=int, default=1500)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--max-attempts", type=int, default=2)
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
            max_depth=5,
            request_budget=args.request_budget,
            max_tasks=20_000,
            max_attempts=args.max_attempts,
            timeout=args.timeout,
            max_document_bytes=2_000_000,
            max_vrm_json_bytes=4_000_000,
            max_links_per_document=500,
        )
        crawler = RecursiveCrawler(store, policy, logger=lambda message: print(message, file=sys.stderr))
        run_id = crawler.new_run({"command": "run_staging_validation_pass.py", "include_avatars": True})
        seeded = crawler.seed_existing_catalog(
            run_id,
            unresolved_only=True,
            include_avatars=True,
        )
        if seeded == 0:
            store.finish_run(run_id, "failed", "no catalog URLs to validate")
            print("error: no catalog URLs to validate", file=sys.stderr)
            return 2
        summary = crawler.run(run_id)
        materialized = crawler.materialize(run_id)
        after = snapshot(store.conn)
        hits = valid_hits(store.conn, run_id)

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
        "run_id": run_id,
        "started_at": started,
        "finished_at": now(),
        "seeded_tasks": seeded,
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
    return 0 if summary.status in {"completed", "budget_exhausted"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
