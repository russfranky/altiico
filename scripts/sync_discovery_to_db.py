#!/usr/bin/env python3
"""Sync crawler evidence into SQLite and build a deterministic promotion queue.

Discovery is allowed to be noisy. Canonical rows are not.

This script makes crawler work visible immediately by storing per-collection
crawl/evidence state in SQLite. It only marks a candidate auto-promotable when
there is explicit binary VRM proof (valid GLB 2.0 plus VRM/VRMC_vrm, SHA-256,
canonical URL). It never promotes claims based only on marketplace/index data.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BASE = Path(__file__).parent.parent
DEFAULT_DB = BASE / "data" / "vrm_index.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS discovery_evidence (
    collection_id TEXT NOT NULL,
    source TEXT NOT NULL,
    observed_at TEXT,
    status TEXT,
    corroborated INTEGER DEFAULT 0,
    conflicts INTEGER DEFAULT 0,
    tokens_sampled INTEGER DEFAULT 0,
    uris_observed INTEGER DEFAULT 0,
    model_signals INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    details_json TEXT,
    PRIMARY KEY (collection_id, source)
);

CREATE TABLE IF NOT EXISTS promotion_candidates (
    candidate_id TEXT PRIMARY KEY,
    collection_id TEXT,
    chain TEXT,
    contract TEXT,
    token_id TEXT,
    name TEXT,
    model_url TEXT,
    canonical_url TEXT,
    source TEXT NOT NULL,
    observed_at TEXT,
    validation_status TEXT NOT NULL,
    vrm_spec TEXT,
    sha256 TEXT,
    byte_length INTEGER,
    promotion_state TEXT NOT NULL,
    reason TEXT,
    evidence_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_promotion_state ON promotion_candidates(promotion_state);
CREATE INDEX IF NOT EXISTS idx_promotion_collection ON promotion_candidates(collection_id);
"""


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def upsert_evidence(conn: sqlite3.Connection, collection_id: str, source: str, **fields: Any) -> None:
    conn.execute(
        """INSERT INTO discovery_evidence
        (collection_id,source,observed_at,status,corroborated,conflicts,tokens_sampled,uris_observed,model_signals,errors,details_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(collection_id,source) DO UPDATE SET
          observed_at=excluded.observed_at,
          status=excluded.status,
          corroborated=excluded.corroborated,
          conflicts=excluded.conflicts,
          tokens_sampled=excluded.tokens_sampled,
          uris_observed=excluded.uris_observed,
          model_signals=excluded.model_signals,
          errors=excluded.errors,
          details_json=excluded.details_json""",
        (
            collection_id,
            source,
            fields.get("observed_at"),
            fields.get("status"),
            int(bool(fields.get("corroborated"))),
            int(fields.get("conflicts") or 0),
            int(fields.get("tokens_sampled") or 0),
            int(fields.get("uris_observed") or 0),
            int(fields.get("model_signals") or 0),
            int(fields.get("errors") or 0),
            json.dumps(fields.get("details") or {}, separators=(",", ":")),
        ),
    )


def iter_validated_candidates(obj: Any, source: str) -> Iterable[dict[str, Any]]:
    """Recursively yield records that contain explicit binary VRM proof."""
    if isinstance(obj, dict):
        status = str(obj.get("status") or obj.get("validation_status") or "").lower()
        spec = obj.get("vrmSpec") or obj.get("vrm_spec") or obj.get("spec")
        sha = obj.get("sha256") or obj.get("contentSha256") or obj.get("wholeSha256") or obj.get("whole_sha256")
        canonical = obj.get("canonicalUrl") or obj.get("canonical_url") or obj.get("canonicalUri") or obj.get("canonical_uri")
        model = obj.get("modelUrl") or obj.get("model_url") or obj.get("url") or canonical
        is_vrm = status in {"ok_vrm", "validated_vrm", "valid_vrm", "valid"} and bool(spec) and bool(sha) and bool(canonical)
        if is_vrm:
            row = dict(obj)
            row["_source"] = source
            yield row
        for value in obj.values():
            yield from iter_validated_candidates(value, source)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_validated_candidates(value, source)


def candidate_id(row: dict[str, Any], source: str) -> str:
    import hashlib
    key = "|".join(str(row.get(k) or "") for k in (
        "chain", "contract", "tokenId", "token_id", "canonicalUrl", "canonical_url", "canonicalUri", "canonical_uri", "sha256", "contentSha256", "wholeSha256"
    )) + "|" + source
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def insert_candidate(conn: sqlite3.Connection, row: dict[str, Any], source: str) -> None:
    canonical = row.get("canonicalUrl") or row.get("canonical_url") or row.get("canonicalUri") or row.get("canonical_uri")
    sha = row.get("sha256") or row.get("contentSha256") or row.get("wholeSha256") or row.get("whole_sha256")
    spec = row.get("vrmSpec") or row.get("vrm_spec") or row.get("spec")
    collection_id = row.get("collectionId") or row.get("collection_id") or row.get("catalogId") or row.get("catalog_id")
    status = str(row.get("status") or row.get("validation_status") or "validated_vrm")
    reason = "binary VRM proof complete; eligible for canonical reconciliation"
    conn.execute(
        """INSERT INTO promotion_candidates
        (candidate_id,collection_id,chain,contract,token_id,name,model_url,canonical_url,source,observed_at,validation_status,vrm_spec,sha256,byte_length,promotion_state,reason,evidence_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(candidate_id) DO UPDATE SET
          collection_id=excluded.collection_id,
          observed_at=excluded.observed_at,
          validation_status=excluded.validation_status,
          vrm_spec=excluded.vrm_spec,
          sha256=excluded.sha256,
          byte_length=excluded.byte_length,
          promotion_state=excluded.promotion_state,
          reason=excluded.reason,
          evidence_json=excluded.evidence_json""",
        (
            candidate_id(row, source), collection_id, row.get("chain"), row.get("contract"),
            row.get("tokenId") or row.get("token_id"), row.get("name"),
            row.get("modelUrl") or row.get("model_url") or row.get("url") or canonical,
            canonical, source, row.get("observedAt") or row.get("observed_at") or datetime.now(timezone.utc).isoformat(),
            status, spec, sha, row.get("bytes") or row.get("byteLength") or row.get("byte_length"),
            "ready_for_reconciliation", reason, json.dumps(row, separators=(",", ":")),
        ),
    )


def sync_authoritative(conn: sqlite3.Connection, path: Path) -> int:
    data = read_json(path)
    if not data:
        return 0
    n = 0
    observed = data.get("generatedAt")
    for row in data.get("collections", []):
        cid = row.get("catalogId")
        if not cid:
            continue
        identity = row.get("identity") or {}
        conflict_count = 0
        for section in (row.get("media") or {}, row.get("stats") or {}, {"name": identity.get("nameObservation") or {}}):
            for value in section.values():
                if isinstance(value, dict) and value.get("status") == "conflict":
                    conflict_count += 1
        explorer = row.get("etherscan") or row.get("explorerEvidence") or {}
        bitquery = row.get("bitquery") or row.get("bitqueryEvidence") or {}
        corroborated = bool(
            explorer.get("corroborated") or explorer.get("contractObserved") or
            bitquery.get("corroborated") or bitquery.get("contractObservedOnchain")
        )
        upsert_evidence(conn, cid, "authoritative_consensus", observed_at=observed,
                        status="conflict" if conflict_count else "observed",
                        corroborated=corroborated, conflicts=conflict_count,
                        details={"identity": identity, "sourceSchema": data.get("schema")})
        n += 1
    return n


def sync_bitquery(conn: sqlite3.Connection, path: Path) -> int:
    data = read_json(path)
    if not data:
        return 0
    n = 0
    for row in data.get("collections", []):
        cid = row.get("catalogId")
        if not cid:
            continue
        upsert_evidence(conn, cid, "bitquery", observed_at=row.get("observedAt") or data.get("generatedAt"),
                        status="observed" if row.get("contractObservedOnchain") else "checked",
                        corroborated=row.get("contractObservedOnchain"),
                        tokens_sampled=row.get("tokensSampled"), uris_observed=row.get("transferUris"),
                        model_signals=len(row.get("modelSignals") or []), errors=len(row.get("errors") or []),
                        details={"supported": row.get("supported"), "uniqueTokenIds": row.get("uniqueTokenIds")})
        n += 1
    return n


def sync_moralis_models(conn: sqlite3.Connection, path: Path) -> int:
    data = read_json(path)
    if not data or data.get("availability") == "unavailable":
        return 0
    n = 0
    for row in data.get("collections", []):
        cid = row.get("catalogId")
        if not cid:
            continue
        nfts = row.get("nfts") or []
        model_signals = sum(len(x.get("candidates") or x.get("modelCandidates") or []) for x in nfts if isinstance(x, dict))
        upsert_evidence(conn, cid, "moralis_models", observed_at=data.get("generatedAt"),
                        status="signals" if model_signals else "checked", model_signals=model_signals,
                        errors=1 if row.get("error") else 0,
                        details={"nftsWithSignals": len([x for x in nfts if x.get("candidates") or x.get("modelCandidates")])})
        n += 1
    return n


def sync_validated_reports(conn: sqlite3.Connection, paths: list[Path]) -> int:
    count = 0
    for path in paths:
        data = read_json(path)
        if not data:
            continue
        for row in iter_validated_candidates(data, path.name):
            insert_candidate(conn, row, path.name)
            count += 1
    return count


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    conn.executescript(SCHEMA)
    evidence = 0
    evidence += sync_authoritative(conn, BASE / "data" / "authoritative_consensus.json")
    evidence += sync_bitquery(conn, BASE / "data" / "bitquery_evidence_report.json")
    evidence += sync_moralis_models(conn, BASE / "data" / "moralis_model_discovery.json")

    candidate_paths = sorted(set(
        list((BASE / "data").glob("*discovery*.json")) +
        list((BASE / "data").glob("*validation*.json")) +
        list((BASE / "data").glob("*audit*.json"))
    ))
    candidates = sync_validated_reports(conn, candidate_paths)
    conn.commit()
    summary = {
        "evidenceRows": conn.execute("SELECT COUNT(*) FROM discovery_evidence").fetchone()[0],
        "collectionsWithEvidence": conn.execute("SELECT COUNT(DISTINCT collection_id) FROM discovery_evidence").fetchone()[0],
        "promotionCandidates": conn.execute("SELECT COUNT(*) FROM promotion_candidates").fetchone()[0],
        "readyForReconciliation": conn.execute("SELECT COUNT(*) FROM promotion_candidates WHERE promotion_state='ready_for_reconciliation'").fetchone()[0],
        "evidenceUpsertsThisRun": evidence,
        "validatedCandidatesSeenThisRun": candidates,
    }
    conn.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
