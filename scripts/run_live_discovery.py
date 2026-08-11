#!/usr/bin/env python3
"""Run a measured live discovery pass over high-signal NFT contracts.

This is deliberately contract- and curation-driven. It expands explicit targets
plus unresolved catalog rows, samples real token IDs, hands those tokens to the
persistent recursive crawler, validates VRM binaries, materializes only bound
hits, and writes an auditable before/after report.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.crawler.engine import RecursiveCrawler  # noqa: E402
from scripts.crawler.fetch import (  # noqa: E402
    EVM_RPCS,
    EvmTokenResolver,
    NetworkLoader,
)
from scripts.crawler.models import (  # noqa: E402
    CrawlPolicy,
    PermanentCrawlError,
    RetryableCrawlError,
)
from scripts.crawler.store import CrawlStore, utc_now  # noqa: E402

TOTAL_SUPPLY_SELECTOR = "0x18160ddd"
TOKEN_BY_INDEX_SELECTOR = "0x4f6ccce7"
SHARED_STOREFRONT = "0x495f947276749ce646f68ac8c248420045cb7b5e"
DEFAULT_FALLBACK_IDS = (0, 1, 2, 3, 4, 5, 10, 25, 50, 100, 250, 500, 1000)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return out or "collection"


def _dedupe(values: Iterable[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for value in values:
        if value < 0 or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_numeric_tail(value: str | None) -> list[int]:
    if not value:
        return []
    clean = value.split("?", 1)[0].rstrip("/")
    found = re.findall(r"(?:^|[/_-])(\d+)(?:\.[A-Za-z0-9]+)?$", clean)
    return [int(item) for item in found]


def _decode_uint(result: Any) -> int | None:
    if not isinstance(result, str) or not result.startswith("0x"):
        return None
    try:
        return int(result, 16)
    except ValueError:
        return None


@dataclass
class Target:
    key: str
    name: str
    collection_id: str
    chain: str
    contract: str
    source: str
    create_collection: bool = False
    token_ids: list[int] = field(default_factory=list)
    vrm_param: str = ""
    notes: str = ""
    sample_metadata_url: str = ""
    total_supply: int | None = None
    token_discovery_requests: int = 0
    resolution: str = ""


class TokenSampler:
    """Discover representative token IDs without assuming IDs start at 0 or 1."""

    def __init__(self, loader: NetworkLoader) -> None:
        self.loader = loader

    def _eth_call(self, chain: str, contract: str, data: str) -> tuple[int | None, int]:
        used_total = 0
        for rpc in EVM_RPCS.get(chain, ()):
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_call",
                "params": [{"to": contract, "data": data}, "latest"],
            }
            try:
                response, used = self.loader.post_json(rpc, payload)
                used_total += used
            except (RetryableCrawlError, PermanentCrawlError) as exc:
                used_total += exc.request_count
                continue
            if not isinstance(response, dict) or response.get("error"):
                continue
            value = _decode_uint(response.get("result"))
            if value is not None:
                return value, used_total
        return None, used_total

    def total_supply(self, target: Target) -> tuple[int | None, int]:
        return self._eth_call(target.chain, target.contract, TOTAL_SUPPLY_SELECTOR)

    def token_by_index(self, target: Target, index: int) -> tuple[int | None, int]:
        data = TOKEN_BY_INDEX_SELECTOR + f"{index:064x}"
        return self._eth_call(target.chain, target.contract, data)

    def sample(self, target: Target, limit: int) -> list[int]:
        candidates: list[int] = list(target.token_ids)
        candidates.extend(_extract_numeric_tail(target.sample_metadata_url))
        supply, used = self.total_supply(target)
        target.token_discovery_requests += used
        target.total_supply = supply

        if supply and supply > 0:
            indices = _dedupe(
                [0, 1, 2, supply // 4, supply // 2, (3 * supply) // 4, supply - 1]
            )
            enumerable_ids: list[int] = []
            for index in indices:
                if index >= supply:
                    continue
                token_id, calls = self.token_by_index(target, index)
                target.token_discovery_requests += calls
                if token_id is not None:
                    enumerable_ids.append(token_id)
            candidates.extend(enumerable_ids)
            candidates.extend([supply - 1, max(0, supply // 2)])

        candidates.extend(DEFAULT_FALLBACK_IDS)
        return _dedupe(candidates)[:limit]


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _snapshot(conn: sqlite3.Connection) -> dict[str, int]:
    def scalar(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    out = {
        "collections": scalar("SELECT COUNT(*) FROM collections"),
        "collections_with_vrm_url": scalar(
            "SELECT COUNT(*) FROM collections WHERE vrm_url_https IS NOT NULL AND vrm_url_https!=''"
        ),
        "collections_validated_vrm": scalar(
            "SELECT COUNT(*) FROM collections WHERE vrm_check_status='ok_vrm'"
        ),
        "contracts": scalar("SELECT COUNT(*) FROM contracts"),
    }
    if _table_exists(conn, "vrm_metadata"):
        out["validated_vrm_assets"] = scalar(
            "SELECT COUNT(*) FROM vrm_metadata WHERE parse_error IS NULL AND vrm_spec IS NOT NULL"
        )
    else:
        out["validated_vrm_assets"] = 0
    return out


def _exact_collection_id(conn: sqlite3.Connection, names: list[str]) -> tuple[str, str]:
    matches: list[sqlite3.Row] = []
    for name in names:
        matches.extend(
            conn.execute(
                "SELECT id, name FROM collections WHERE lower(name)=lower(?)", (name,)
            ).fetchall()
        )
    unique = {str(row["id"]): row for row in matches}
    if len(unique) == 1:
        row = next(iter(unique.values()))
        return str(row["id"]), f"exact-name:{row['name']}"
    if len(unique) > 1:
        raise ValueError(f"ambiguous exact collection names {names!r}: {sorted(unique)}")
    return "", "not-found"


def _load_explicit_targets(conn: sqlite3.Connection, config: dict[str, Any]) -> list[Target]:
    targets: list[Target] = []
    for index, raw in enumerate(config.get("targets") or []):
        if not raw.get("enabled", True):
            continue
        chain = str(raw.get("chain") or "ethereum").lower()
        contract = str(raw.get("contract") or "").lower()
        if chain not in EVM_RPCS or not re.fullmatch(r"0x[a-f0-9]{40}", contract):
            raise ValueError(f"invalid target chain/contract at index {index}: {chain}:{contract}")
        collection_id = str(raw.get("collection_id") or "")
        resolution = "explicit-id" if collection_id else ""
        if collection_id:
            if conn.execute("SELECT 1 FROM collections WHERE id=?", (collection_id,)).fetchone() is None:
                raise ValueError(f"configured collection_id does not exist: {collection_id}")
        else:
            names = [str(item) for item in (raw.get("match_names") or []) if item]
            if names:
                collection_id, resolution = _exact_collection_id(conn, names)
        create_collection = bool(raw.get("create_collection", False))
        name = str(raw.get("name") or (raw.get("match_names") or [contract])[0])
        if not collection_id and not create_collection:
            collection_id = f"unbound:{_slugify(name)}:{contract[2:10]}"
            resolution = "unbound"
        elif not collection_id:
            collection_id = str(raw.get("new_collection_id") or f"live-{contract[2:10]}")
            resolution = "proposed-new"
        targets.append(
            Target(
                key=f"config:{index}:{chain}:{contract}",
                name=name,
                collection_id=collection_id,
                chain=chain,
                contract=contract,
                source=str(raw.get("source") or "live-discovery-config"),
                create_collection=create_collection,
                token_ids=[int(item) for item in (raw.get("token_ids") or [])],
                vrm_param=str(raw.get("vrm_param") or ""),
                notes=str(raw.get("notes") or ""),
                resolution=resolution,
            )
        )
    return targets


def _load_auto_targets(
    conn: sqlite3.Connection, config: dict[str, Any], existing_keys: set[tuple[str, str]],
) -> list[Target]:
    auto = config.get("auto_existing") or {}
    if not auto.get("enabled", True):
        return []
    limit = max(0, int(auto.get("limit", 30)))
    tiers = [str(item).upper() for item in (auto.get("tiers") or ["A", "B", "C"])]
    placeholders = ",".join("?" for _ in tiers)
    sql = f"""
        SELECT id, name, chain, contract, vrm_param, notes, sample_metadata_url,
               vrm_check_status, tier
        FROM collections
        WHERE tier IN ({placeholders})
          AND contract IS NOT NULL AND contract!=''
          AND lower(contract)!=?
          AND (vrm_check_status IS NULL OR vrm_check_status!='ok_vrm')
          AND (
              tier='A'
              OR (vrm_param IS NOT NULL AND vrm_param!='')
              OR (sample_metadata_url IS NOT NULL AND sample_metadata_url!='')
              OR lower(COALESCE(notes,'')) LIKE '%vrm%'
          )
        ORDER BY
          CASE tier WHEN 'A' THEN 0 WHEN 'B' THEN 1 ELSE 2 END,
          CASE WHEN vrm_param IS NOT NULL AND vrm_param!='' THEN 0 ELSE 1 END,
          name
    """
    params: list[Any] = [*tiers, SHARED_STOREFRONT]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    out: list[Target] = []
    for row in conn.execute(sql, params):
        chain = str(row["chain"] or "").lower()
        contract = str(row["contract"] or "").lower()
        if chain not in EVM_RPCS or not re.fullmatch(r"0x[a-f0-9]{40}", contract):
            continue
        if (chain, contract) in existing_keys:
            continue
        out.append(
            Target(
                key=f"catalog:{row['id']}",
                name=str(row["name"]),
                collection_id=str(row["id"]),
                chain=chain,
                contract=contract,
                source="live-discovery:auto-existing",
                vrm_param=str(row["vrm_param"] or ""),
                notes=str(row["notes"] or ""),
                sample_metadata_url=str(row["sample_metadata_url"] or ""),
                resolution="existing-id",
            )
        )
    return out


def _insert_new_collection(conn: sqlite3.Connection, target: Target, hit: dict[str, Any]) -> bool:
    if not target.create_collection:
        return False
    if conn.execute("SELECT 1 FROM collections WHERE id=?", (target.collection_id,)).fetchone():
        return False
    columns = _table_columns(conn, "collections")
    fields: dict[str, Any] = {
        "id": target.collection_id,
        "name": target.name,
        "tier": "A",
        "chain": target.chain,
        "contract": target.contract,
        "vrm_param": target.vrm_param or hit.get("json_path") or "recursive metadata",
        "source": target.source,
        "notes": (
            f"Validated by live recursive crawl from {target.chain}:{target.contract}; "
            f"token {hit.get('token_id')}. {target.notes}"
        ).strip(),
        "license_category": "unknown",
        "commercial_use": "unknown",
        "allowed_user": "unknown",
        "redistribution": "unknown",
    }
    clean = {key: value for key, value in fields.items() if key in columns}
    names = ", ".join(clean)
    marks = ", ".join("?" for _ in clean)
    conn.execute(f"INSERT INTO collections ({names}) VALUES ({marks})", tuple(clean.values()))
    return True


def _attach_contract(conn: sqlite3.Connection, target: Target) -> bool:
    if target.collection_id.startswith("unbound:"):
        return False
    if not _table_exists(conn, "contracts"):
        return False
    before = conn.execute(
        "SELECT 1 FROM contracts WHERE collection_id=? AND lower(address)=lower(?)",
        (target.collection_id, target.contract),
    ).fetchone()
    if before:
        return False
    columns = _table_columns(conn, "contracts")
    fields: dict[str, Any] = {
        "collection_id": target.collection_id,
        "address": target.contract,
        "chain": target.chain,
        "token_standard": None,
        "is_primary": 0,
    }
    clean = {key: value for key, value in fields.items() if key in columns}
    conn.execute(
        f"INSERT INTO contracts ({', '.join(clean)}) VALUES ({', '.join('?' for _ in clean)})",
        tuple(clean.values()),
    )
    return True


def _valid_hits(conn: sqlite3.Connection, run_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT b.collection_id, b.seed_source, t.id AS task_id,
               t.kind, t.canonical_key, t.payload_json, o.value_json,
               o.source_url, o.json_path, o.confidence
        FROM crawl_observations o
        JOIN crawl_tasks t ON t.id=o.task_id
        JOIN crawl_bindings b ON b.task_id=t.id
        WHERE o.run_id=? AND o.predicate='valid_vrm'
        ORDER BY b.collection_id, t.id
        """,
        (run_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        value = json.loads(row["value_json"])
        payload = json.loads(row["payload_json"])
        token_id = payload.get("token_id")
        if token_id is None:
            match = re.match(r"evm:[^:]+:0x[a-f0-9]{40}:(\d+)$", str(row["canonical_key"]))
            token_id = int(match.group(1)) if match else None
        out.append(
            {
                "collection_id": row["collection_id"],
                "seed_source": row["seed_source"],
                "task_id": row["task_id"],
                "task_kind": row["kind"],
                "token_id": token_id,
                "canonical_url": value.get("canonical_url"),
                "transport_url": value.get("transport_url"),
                "vrm_spec": value.get("vrm_spec"),
                "total_length": value.get("total_length"),
                "json_path": row["json_path"],
                "source_url": row["source_url"],
                "confidence": row["confidence"],
            }
        )
    return out


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    delta = report["delta"]
    lines = [
        f"# Live VRM discovery run {report['run_id']}",
        "",
        f"Run at: `{report['finished_at']}`",
        "",
        "## Outcome",
        "",
        f"- New catalog collections: **{delta['collections']}**",
        f"- Newly validated collection rows: **{delta['collections_validated_vrm']}**",
        f"- New validated VRM assets: **{delta['validated_vrm_assets']}**",
        f"- New contract associations: **{delta['contracts']}**",
        f"- Validated hits in this run: **{len(report['hits'])}**",
        "",
        "## Hits",
        "",
    ]
    if report["hits"]:
        lines.append("| Collection | Token | VRM | Spec | Evidence |")
        lines.append("|---|---:|---|---|---|")
        for hit in report["hits"]:
            lines.append(
                f"| `{hit['collection_id']}` | {hit.get('token_id') if hit.get('token_id') is not None else ''} "
                f"| `{hit.get('canonical_url') or ''}` | {hit.get('vrm_spec') or ''} "
                f"| `{hit.get('source_url') or ''}{hit.get('json_path') or ''}` |"
            )
    else:
        lines.append("No VRM binary passed validation in this run.")
    lines.extend(["", "## Targets", ""])
    lines.append("| Target | Binding | Contract | Tokens sampled | Result |")
    lines.append("|---|---|---|---:|---|")
    hit_ids = {hit["collection_id"] for hit in report["hits"]}
    for target in report["targets"]:
        result = "validated VRM" if target["collection_id"] in hit_ids else "no validated hit"
        lines.append(
            f"| {target['name']} | `{target['collection_id']}` | "
            f"`{target['chain']}:{target['contract']}` | {len(target['token_ids'])} | {result} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db).resolve()
    config_path = Path(args.targets).resolve()
    report_path = Path(args.report).resolve()
    markdown_path = Path(args.markdown_report).resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    policy_cfg = config.get("policy") or {}
    policy = CrawlPolicy(
        max_depth=int(policy_cfg.get("max_depth", 5)),
        request_budget=int(args.request_budget or policy_cfg.get("request_budget", 2500)),
        max_tasks=int(policy_cfg.get("max_tasks", 15000)),
        max_attempts=int(policy_cfg.get("max_attempts", 3)),
        timeout=float(policy_cfg.get("timeout", 20.0)),
        max_document_bytes=int(policy_cfg.get("max_document_bytes", 2_000_000)),
        max_vrm_json_bytes=int(policy_cfg.get("max_vrm_json_bytes", 4_000_000)),
        max_links_per_document=int(policy_cfg.get("max_links_per_document", 500)),
    )
    token_limit = int(args.token_sample_limit or config.get("token_sample_limit", 12))

    with CrawlStore(db_path) as store:
        store.ensure_schema()
        conn = store.conn
        before = _snapshot(conn)
        explicit = _load_explicit_targets(conn, config)
        explicit_keys = {(item.chain, item.contract) for item in explicit}
        automatic = _load_auto_targets(conn, config, explicit_keys)
        targets = explicit + automatic
        if args.max_targets:
            targets = targets[: args.max_targets]

        crawler = RecursiveCrawler(store, policy, logger=lambda message: print(message, file=sys.stderr))
        sampler = TokenSampler(crawler.loader)
        run_id = crawler.new_run(
            {
                "command": "run_live_discovery.py",
                "targets_file": str(config_path.relative_to(_REPO_ROOT))
                if config_path.is_relative_to(_REPO_ROOT)
                else str(config_path),
                "token_sample_limit": token_limit,
                "target_count": len(targets),
            }
        )

        discovery_requests = 0
        for target in targets:
            print(f"[seed] {target.name}: {target.chain}:{target.contract}", file=sys.stderr)
            token_ids = sampler.sample(target, token_limit)
            target.token_ids = token_ids
            discovery_requests += target.token_discovery_requests
            if target.sample_metadata_url:
                try:
                    crawler.seed_metadata(
                        run_id,
                        target.sample_metadata_url,
                        collection_id=target.collection_id,
                        source=f"{target.source}:sample_metadata",
                    )
                except PermanentCrawlError as exc:
                    print(f"  sample metadata skipped: {exc}", file=sys.stderr)
            for token_id in token_ids:
                crawler.seed_evm_token(
                    run_id,
                    target.chain,
                    target.contract,
                    token_id,
                    collection_id=target.collection_id,
                    source=target.source,
                )

        summary = crawler.run(run_id)
        hits = _valid_hits(conn, run_id)
        target_by_id = {target.collection_id: target for target in targets}
        created: list[str] = []
        attached_contracts: list[str] = []

        first_hit_by_id: dict[str, dict[str, Any]] = {}
        for hit in hits:
            first_hit_by_id.setdefault(hit["collection_id"], hit)
        with store.transaction():
            for collection_id, hit in first_hit_by_id.items():
                target = target_by_id.get(collection_id)
                if target is None or collection_id.startswith("unbound:"):
                    continue
                if _insert_new_collection(conn, target, hit):
                    created.append(collection_id)
                if _attach_contract(conn, target):
                    attached_contracts.append(f"{collection_id}:{target.chain}:{target.contract}")

        materialized = crawler.materialize(run_id)
        summary.materialized_collections = materialized
        after = _snapshot(conn)

        delta = {key: after.get(key, 0) - before.get(key, 0) for key in sorted(set(before) | set(after))}
        report = {
            "run_id": run_id,
            "started_at": dict(store.get_run(run_id)).get("started_at"),
            "finished_at": _utc_iso(),
            "summary": asdict(summary),
            "token_discovery_requests": discovery_requests,
            "before": before,
            "after": after,
            "delta": delta,
            "created_collections": created,
            "attached_contracts": attached_contracts,
            "hits": hits,
            "targets": [asdict(target) for target in targets],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _write_markdown(report, markdown_path)

    if args.build:
        subprocess.run(
            [sys.executable, str(_REPO_ROOT / "scripts" / "build_catalog.py"), "--db", str(db_path)],
            check=True,
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a measured live VRM discovery pass")
    parser.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    parser.add_argument("--targets", default=str(_REPO_ROOT / "data" / "live_discovery_targets.yaml"))
    parser.add_argument("--report", default=str(_REPO_ROOT / "data" / "live_discovery_report.json"))
    parser.add_argument(
        "--markdown-report", default=str(_REPO_ROOT / "docs" / "live-discovery-latest.md")
    )
    parser.add_argument("--request-budget", type=int, default=0)
    parser.add_argument("--token-sample-limit", type=int, default=0)
    parser.add_argument("--max-targets", type=int, default=0)
    parser.add_argument("--build", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
