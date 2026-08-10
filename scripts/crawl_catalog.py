#!/usr/bin/env python3
"""Run the persistent recursive VRM catalog crawler.

The crawler is seed-driven. It follows metadata documents recursively, validates
candidate assets by reading only the GLB header and JSON chunk, records a durable
evidence graph, and materializes only into explicitly bound catalog records.

Examples:
    python scripts/crawl_catalog.py run --seed-existing --unresolved-only
    python scripts/crawl_catalog.py run --metadata-url ipfs://CID/1.json \
        --collection-id my-collection --build
    python scripts/crawl_catalog.py run \
        --evm-token ethereum:0xabc...:42 --collection-id my-collection
    python scripts/crawl_catalog.py run --resume 12 --request-budget 5000
    python scripts/crawl_catalog.py status 12
    python scripts/crawl_catalog.py explain 12 my-collection
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.crawler.engine import RecursiveCrawler, load_seed_file  # noqa: E402
from scripts.crawler.models import CrawlPolicy  # noqa: E402
from scripts.crawler.store import CrawlStore  # noqa: E402

_DEFAULT_DB = _REPO_ROOT / "data" / "vrm_index.db"


def _policy(args: argparse.Namespace) -> CrawlPolicy:
    return CrawlPolicy(
        max_depth=args.max_depth,
        request_budget=args.request_budget,
        max_tasks=args.max_tasks,
        max_attempts=args.max_attempts,
        timeout=args.timeout,
        max_document_bytes=args.max_document_bytes,
        max_vrm_json_bytes=args.max_vrm_json_bytes,
        max_links_per_document=args.max_links_per_document,
    )


def _parse_evm_seed(value: str) -> tuple[str, str, int]:
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "EVM token must be CHAIN:0xCONTRACT:TOKEN_ID"
        )
    chain, contract, raw_id = parts
    try:
        token_id = int(raw_id, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid token id: {raw_id}") from exc
    return chain, contract, token_id


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def cmd_run(args: argparse.Namespace) -> int:
    db = Path(args.db)
    if not db.exists():
        print(f"error: database not found: {db}", file=sys.stderr)
        return 2

    policy = _policy(args)
    with CrawlStore(db) as store:
        store.ensure_schema()
        crawler = RecursiveCrawler(
            store,
            policy,
            logger=(lambda message: None) if args.quiet else (lambda message: print(message, file=sys.stderr)),
        )

        if args.resume is not None:
            run_id = args.resume
            summary = crawler.run(run_id, resume=True)
        else:
            run_id = crawler.new_run(
                {
                    "command": "crawl_catalog.py run",
                    "seed_existing": args.seed_existing,
                    "unresolved_only": args.unresolved_only,
                    "include_avatars": args.include_avatars,
                }
            )
            seeded = 0
            if args.seed_existing:
                seeded += crawler.seed_existing_catalog(
                    run_id,
                    unresolved_only=args.unresolved_only,
                    include_avatars=args.include_avatars,
                    collection_limit=args.collection_limit,
                    avatar_limit=args.avatar_limit,
                )
            for url in args.metadata_url:
                crawler.seed_metadata(
                    run_id,
                    url,
                    collection_id=args.collection_id,
                    avatar_id=args.avatar_id,
                    source="cli:metadata",
                )
                seeded += 1
            for url in args.asset_url:
                crawler.seed_asset(
                    run_id,
                    url,
                    collection_id=args.collection_id,
                    avatar_id=args.avatar_id,
                    source="cli:asset",
                )
                seeded += 1
            for chain, contract, token_id in args.evm_token:
                crawler.seed_evm_token(
                    run_id,
                    chain,
                    contract,
                    token_id,
                    collection_id=args.collection_id,
                    avatar_id=args.avatar_id,
                    source="cli:evm_token",
                )
                seeded += 1
            for seed_file in args.seed_file:
                seeded += crawler.seed_records(run_id, load_seed_file(seed_file))
            if seeded == 0:
                store.finish_run(run_id, "failed", "no seeds supplied")
                print(
                    "error: provide --seed-existing, --metadata-url, --asset-url, "
                    "--evm-token, or --seed-file",
                    file=sys.stderr,
                )
                return 2
            summary = crawler.run(run_id)

        if not args.no_materialize:
            summary.materialized_collections = crawler.materialize(run_id)

        if args.build:
            subprocess.run(
                [sys.executable, str(_REPO_ROOT / "scripts" / "build_catalog.py"), "--db", str(db)],
                check=True,
            )

        _emit(asdict(summary))
    return 0 if summary.status in {"completed", "budget_exhausted"} else 1


def cmd_status(args: argparse.Namespace) -> int:
    with CrawlStore(args.db) as store:
        store.ensure_schema()
        run = dict(store.get_run(args.run_id))
        run["config"] = json.loads(run.pop("config_json"))
        run["task_counts"] = store.task_counts(args.run_id)
        run["observations"] = store.observation_count(args.run_id)
        run["pending"] = store.pending_count(args.run_id)
        _emit(run)
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    with CrawlStore(args.db) as store:
        store.ensure_schema()
        _emit(
            {
                "run_id": args.run_id,
                "collection_id": args.collection_id,
                "evidence": store.explain_collection(args.run_id, args.collection_id),
            }
        )
    return 0


def cmd_materialize(args: argparse.Namespace) -> int:
    with CrawlStore(args.db) as store:
        store.ensure_schema()
        count = store.materialize_valid_vrms(args.run_id)
        _emit({"run_id": args.run_id, "materialized_collections": count})
    return 0


def _add_policy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--request-budget", type=int, default=2_000)
    parser.add_argument("--max-tasks", type=int, default=20_000)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--max-document-bytes", type=int, default=2_000_000)
    parser.add_argument("--max-vrm-json-bytes", type=int, default=4_000_000)
    parser.add_argument("--max-links-per-document", type=int, default=500)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent recursive VRM catalog crawler")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="create or resume a crawl run")
    run.add_argument("--db", default=str(_DEFAULT_DB))
    run.add_argument("--resume", type=int, help="resume an existing run id")
    run.add_argument("--seed-existing", action="store_true",
                     help="seed concrete metadata/VRM URLs already in the catalog")
    run.add_argument("--unresolved-only", action="store_true",
                     help="with --seed-existing, skip collections already marked ok_vrm")
    run.add_argument("--include-avatars", action="store_true",
                     help="also seed every bound avatar model_file_url")
    run.add_argument("--collection-limit", type=int, default=0)
    run.add_argument("--avatar-limit", type=int, default=0)
    run.add_argument("--metadata-url", action="append", default=[])
    run.add_argument("--asset-url", action="append", default=[])
    run.add_argument("--evm-token", action="append", type=_parse_evm_seed, default=[],
                     metavar="CHAIN:CONTRACT:TOKEN_ID")
    run.add_argument("--seed-file", action="append", default=[],
                     help="JSON array or JSONL file containing explicit typed seeds")
    run.add_argument("--collection-id", default="",
                     help="binding applied to direct CLI seeds; never inferred from a name")
    run.add_argument("--avatar-id", default="")
    run.add_argument("--no-materialize", action="store_true")
    run.add_argument("--build", action="store_true",
                     help="run scripts/build_catalog.py after materialization")
    run.add_argument("--quiet", action="store_true")
    _add_policy_args(run)
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="show durable run state")
    status.add_argument("run_id", type=int)
    status.add_argument("--db", default=str(_DEFAULT_DB))
    status.set_defaults(func=cmd_status)

    explain = sub.add_parser("explain", help="show evidence bound to one collection")
    explain.add_argument("run_id", type=int)
    explain.add_argument("collection_id")
    explain.add_argument("--db", default=str(_DEFAULT_DB))
    explain.set_defaults(func=cmd_explain)

    materialize = sub.add_parser("materialize", help="apply valid evidence transactionally")
    materialize.add_argument("run_id", type=int)
    materialize.add_argument("--db", default=str(_DEFAULT_DB))
    materialize.set_defaults(func=cmd_materialize)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
