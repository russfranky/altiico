#!/usr/bin/env python3
"""Audit every concrete VRM link in the canonical catalog.

The audit reads the SQLite catalog and generated JSON projections, deduplicates
links by canonical URI, probes each available transport, validates the complete
GLB/VRM binary, and writes machine-readable and human-readable reports.

It is intentionally read-only. Link repairs should be reviewed separately
because a gateway outage is not the same thing as a bad content identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.crawler.fetch import NetworkLoader  # noqa: E402
from scripts.crawler.models import (  # noqa: E402
    CrawlPolicy,
    PermanentCrawlError,
    RetryableCrawlError,
)
from scripts.crawler.uri import canonicalize_uri, transport_candidates  # noqa: E402

_URL_PREFIXES = (
    "http://",
    "https://",
    "ipfs://",
    "ipns://",
    "ar://",
    "arweave://",
)
_TEMPLATE_MARKERS = ("{token_id}", "{id}", "%d", "${", "{{")
_VRM_KEY_FRAGMENTS = (
    "vrm",
    "model_file",
    "model_url",
    "asset_url",
    "source_url",
    "originalsourceurl",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _looks_like_url(value: str) -> bool:
    return value.strip().lower().startswith(_URL_PREFIXES)


def _has_template(value: str) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in _TEMPLATE_MARKERS)


def _looks_like_vrm(value: str, key_hint: str = "") -> bool:
    raw = value.strip()
    if not _looks_like_url(raw):
        return False
    path = urllib.parse.urlsplit(raw).path.lower()
    key = key_hint.lower().replace("_", "")
    return path.endswith(".vrm") or any(
        fragment.replace("_", "") in key for fragment in _VRM_KEY_FRAGMENTS
    )


def _empty_candidate(raw: str, canonical: str | None) -> dict[str, Any]:
    return {
        "canonical_url": canonical,
        "raw_urls": {raw},
        "origins": set(),
        "collection_ids": set(),
        "avatar_ids": set(),
        "token_ids": set(),
        "references": [],
    }


def _add_candidate(
    registry: dict[str, dict[str, Any]],
    invalid: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    *,
    raw_url: str,
    origin: str,
    collection_id: str | None = None,
    avatar_id: str | None = None,
    token_id: str | None = None,
) -> None:
    raw = str(raw_url or "").strip()
    if not raw:
        return
    if _has_template(raw):
        templates.append(
            {
                "template": raw,
                "origin": origin,
                "collection_id": collection_id,
            }
        )
        return
    try:
        canonical = canonicalize_uri(raw)
    except (PermanentCrawlError, RetryableCrawlError) as exc:
        invalid.append(
            {
                "raw_url": raw,
                "origin": origin,
                "collection_id": collection_id,
                "avatar_id": avatar_id,
                "token_id": token_id,
                "error_class": exc.error_class,
                "error": str(exc),
            }
        )
        return

    entry = registry.setdefault(canonical, _empty_candidate(raw, canonical))
    entry["raw_urls"].add(raw)
    entry["origins"].add(origin)
    if collection_id:
        entry["collection_ids"].add(str(collection_id))
    if avatar_id:
        entry["avatar_ids"].add(str(avatar_id))
    if token_id is not None and str(token_id) != "":
        entry["token_ids"].add(str(token_id))
    entry["references"].append(
        {
            "origin": origin,
            "raw_url": raw,
            "collection_id": collection_id,
            "avatar_id": avatar_id,
            "token_id": token_id,
        }
    )


def collect_from_db(
    conn: sqlite3.Connection,
    registry: dict[str, dict[str, Any]],
    invalid: list[dict[str, Any]],
    templates: list[dict[str, Any]],
) -> None:
    conn.row_factory = sqlite3.Row

    collection_columns = _columns(conn, "collections")
    collection_url_columns = [
        name
        for name in (
            "vrm_url",
            "vrm_url_https",
            "vrm_url_pattern",
            "sample_vrm_url",
        )
        if name in collection_columns
    ]
    if collection_url_columns:
        selected = ", ".join(f'"{name}"' for name in collection_url_columns)
        for row in conn.execute(f'SELECT id, {selected} FROM collections ORDER BY id'):
            for column in collection_url_columns:
                value = row[column]
                if value and (_looks_like_vrm(str(value), column) or _has_template(str(value))):
                    _add_candidate(
                        registry,
                        invalid,
                        templates,
                        raw_url=str(value),
                        origin=f"db:collections.{column}",
                        collection_id=str(row["id"]),
                    )

    avatar_columns = _columns(conn, "avatars")
    avatar_url_columns = [
        name
        for name in ("model_file_url", "vrm_url", "source_url")
        if name in avatar_columns
    ]
    if avatar_url_columns:
        select_columns = ["id"]
        for optional in ("collection_id", "token_id"):
            if optional in avatar_columns:
                select_columns.append(optional)
        select_columns.extend(avatar_url_columns)
        selected = ", ".join(f'"{name}"' for name in select_columns)
        for row in conn.execute(f"SELECT {selected} FROM avatars ORDER BY id"):
            for column in avatar_url_columns:
                value = row[column]
                if value and _looks_like_vrm(str(value), column):
                    _add_candidate(
                        registry,
                        invalid,
                        templates,
                        raw_url=str(value),
                        origin=f"db:avatars.{column}",
                        collection_id=(
                            str(row["collection_id"])
                            if "collection_id" in row.keys() and row["collection_id"]
                            else None
                        ),
                        avatar_id=str(row["id"]),
                        token_id=(
                            str(row["token_id"])
                            if "token_id" in row.keys() and row["token_id"] is not None
                            else None
                        ),
                    )

    if _table_exists(conn, "avatar_vrm"):
        columns = _columns(conn, "avatar_vrm")
        url_column = "vrm_source_url" if "vrm_source_url" in columns else None
        if url_column:
            has_avatars = _table_exists(conn, "avatars")
            if has_avatars:
                sql = """
                    SELECT av.avatar_id, av.vrm_source_url,
                           a.collection_id, a.token_id
                    FROM avatar_vrm av
                    LEFT JOIN avatars a ON a.id=av.avatar_id
                    ORDER BY av.avatar_id, av.vrm_source_url
                """
            else:
                sql = """
                    SELECT avatar_id, vrm_source_url,
                           NULL AS collection_id, NULL AS token_id
                    FROM avatar_vrm
                    ORDER BY avatar_id, vrm_source_url
                """
            for row in conn.execute(sql):
                if row["vrm_source_url"]:
                    _add_candidate(
                        registry,
                        invalid,
                        templates,
                        raw_url=str(row["vrm_source_url"]),
                        origin="db:avatar_vrm.vrm_source_url",
                        collection_id=(
                            str(row["collection_id"]) if row["collection_id"] else None
                        ),
                        avatar_id=str(row["avatar_id"]) if row["avatar_id"] else None,
                        token_id=(
                            str(row["token_id"]) if row["token_id"] is not None else None
                        ),
                    )

    if _table_exists(conn, "vrm_metadata"):
        columns = _columns(conn, "vrm_metadata")
        for column in ("source_url", "canonical_url"):
            if column not in columns:
                continue
            for row in conn.execute(
                f'SELECT "{column}" AS url FROM vrm_metadata '
                f'WHERE "{column}" IS NOT NULL AND "{column}" != "" '
                f'ORDER BY "{column}"'
            ):
                value = str(row["url"])
                if _looks_like_vrm(value, column):
                    _add_candidate(
                        registry,
                        invalid,
                        templates,
                        raw_url=value,
                        origin=f"db:vrm_metadata.{column}",
                    )


def _walk_json(value: Any, path: str = "$", key_hint: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield from _walk_json(child, child_path, str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json(child, f"{path}[{index}]", key_hint)
    elif isinstance(value, str):
        yield path, key_hint, value


def _binding_from_json_path(document: Any, path: str) -> tuple[str | None, str | None, str | None]:
    if not isinstance(document, dict):
        return None, None, None
    collection_id = (
        document.get("setSlug")
        or document.get("collection_id")
        or document.get("collectionId")
        or document.get("slug")
    )
    return (str(collection_id) if collection_id else None, None, None)


def collect_from_json(
    roots: list[Path],
    registry: dict[str, dict[str, Any]],
    invalid: list[dict[str, Any]],
    templates: list[dict[str, Any]],
) -> list[str]:
    scanned: list[str] = []
    seen_paths: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(root.rglob("*.json"))
        for path in paths:
            if path in seen_paths:
                continue
            seen_paths.add(path)
            if any(part in {"cache", "os_scrape", "superyeti_archive", "superyeti_archive_wayback"} for part in path.parts):
                continue
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            rel = str(path.relative_to(_ROOT))
            scanned.append(rel)
            base_collection, _, _ = _binding_from_json_path(document, "$")
            for json_path, key_hint, value in _walk_json(document):
                if not (_looks_like_vrm(value, key_hint) or _has_template(value)):
                    continue
                collection_id = base_collection
                avatar_id = None
                token_id = None

                if isinstance(document, dict) and json_path.startswith("$.avatars["):
                    try:
                        index = int(json_path.split("[", 1)[1].split("]", 1)[0])
                        avatar = (document.get("avatars") or [])[index]
                    except (ValueError, IndexError, TypeError):
                        avatar = None
                    if isinstance(avatar, dict):
                        avatar_id = str(avatar.get("id")) if avatar.get("id") else None
                        token_id = (
                            str(avatar.get("tokenId"))
                            if avatar.get("tokenId") is not None
                            else None
                        )
                        collection_id = (
                            str(document.get("setSlug"))
                            if document.get("setSlug")
                            else collection_id
                        )

                _add_candidate(
                    registry,
                    invalid,
                    templates,
                    raw_url=value,
                    origin=f"json:{rel}:{json_path}",
                    collection_id=collection_id,
                    avatar_id=avatar_id,
                    token_id=token_id,
                )
    return scanned


def _probe_transport(
    loader: NetworkLoader,
    transport: str,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = loader._request_transport(
            transport,
            headers={"Range": "bytes=0-19", "Accept": "*/*"},
            max_bytes=20,
            allow_truncate=True,
        )
        magic = result.body[:4]
        return {
            "transport_url": transport,
            "ok": True,
            "http_status": result.http_status,
            "content_type": result.content_type,
            "bytes_observed": len(result.body),
            "glb_magic": magic == b"glTF",
            "magic_hex": magic.hex(),
            "latency_seconds": round(time.monotonic() - started, 3),
            "network_requests": result.network_requests,
        }
    except (RetryableCrawlError, PermanentCrawlError) as exc:
        return {
            "transport_url": transport,
            "ok": False,
            "retryable": bool(exc.retryable),
            "error_class": exc.error_class,
            "error": str(exc),
            "latency_seconds": round(time.monotonic() - started, 3),
            "network_requests": exc.request_count,
        }
    except Exception as exc:
        return {
            "transport_url": transport,
            "ok": False,
            "retryable": False,
            "error_class": "internal_error",
            "error": f"{type(exc).__name__}: {exc}",
            "latency_seconds": round(time.monotonic() - started, 3),
            "network_requests": 0,
        }


def _validate(
    loader: NetworkLoader,
    canonical_url: str,
    max_attempts: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        started = time.monotonic()
        try:
            result = loader.validate_vrm(canonical_url)
            value = asdict(result)
            value["attempts"] = attempt
            value["latency_seconds"] = round(time.monotonic() - started, 3)
            return value, errors
        except RetryableCrawlError as exc:
            errors.append(
                {
                    "attempt": attempt,
                    "retryable": True,
                    "error_class": exc.error_class,
                    "error": str(exc),
                    "network_requests": exc.request_count,
                    "retry_after": exc.retry_after,
                    "latency_seconds": round(time.monotonic() - started, 3),
                }
            )
            if attempt < max_attempts:
                delay = exc.retry_after if exc.retry_after is not None else 2 ** (attempt - 1)
                time.sleep(min(5.0, max(0.0, float(delay))))
        except PermanentCrawlError as exc:
            errors.append(
                {
                    "attempt": attempt,
                    "retryable": False,
                    "error_class": exc.error_class,
                    "error": str(exc),
                    "network_requests": exc.request_count,
                    "latency_seconds": round(time.monotonic() - started, 3),
                }
            )
            break
        except Exception as exc:
            errors.append(
                {
                    "attempt": attempt,
                    "retryable": False,
                    "error_class": "internal_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "network_requests": 0,
                    "latency_seconds": round(time.monotonic() - started, 3),
                }
            )
            break
    return None, errors


def _classification(
    canonical_url: str,
    probes: list[dict[str, Any]],
    validation: dict[str, Any] | None,
    errors: list[dict[str, Any]],
) -> tuple[str, str, str]:
    probe_failures = [probe for probe in probes if not probe.get("ok")]
    probe_successes = [probe for probe in probes if probe.get("ok")]
    first_transport = probes[0]["transport_url"] if probes else ""
    final_transport = str((validation or {}).get("transport_url") or "")

    if validation and validation.get("valid"):
        degraded = bool(probe_failures)
        fallback = bool(first_transport and final_transport and final_transport != first_transport)
        if degraded or fallback:
            return (
                "healthy_with_transport_degradation",
                "warning",
                "Keep the canonical content URI and rely on multiple gateways; at least one transport is degraded.",
            )
        return ("healthy", "info", "No repair required.")

    if validation:
        status = str(validation.get("status") or "")
        if status == "valid_glb_not_vrm":
            return (
                "non_vrm_glb",
                "error",
                "Do not stage this asset as VRM. Inspect token metadata for a different model pointer.",
            )
        if status == "not_glb":
            return (
                "not_glb",
                "error",
                "The URL does not return a GLB 2.0 binary. Replace the pointer or restore the original VRM.",
            )
        if status == "invalid_glb":
            return (
                "invalid_glb",
                "error",
                "The GLB is malformed, truncated, or changed between range requests. Re-upload and update provenance.",
            )
        return (
            "validation_rejected",
            "error",
            "Review the structural validation error and replace or quarantine the asset.",
        )

    classes = {
        str(item.get("error_class") or "")
        for item in [*probe_failures, *errors]
        if item.get("error_class")
    }
    if classes and classes <= {"http_404", "http_410"}:
        return (
            "missing",
            "error",
            "The referenced CID/path or HTTP object is missing. Verify case-sensitive paths and metadata provenance.",
        )
    if classes and classes <= {"http_401", "http_403"}:
        return (
            "access_blocked",
            "error",
            "The source is not publicly retrievable. Move the VRM to durable public storage or use an authorized server-side source.",
        )
    if classes & {"blocked_destination", "blocked_uri", "unsupported_scheme", "invalid_uri"}:
        return (
            "blocked_or_invalid_uri",
            "error",
            "Correct the URI. Local, credential-bearing, private-network, or unsupported destinations are intentionally blocked.",
        )
    if probe_successes and classes:
        return (
            "unstable_transport",
            "warning",
            "A header probe succeeded but complete validation failed. Retry and inspect range support, content length, and gateway consistency.",
        )
    if classes & {"timeout", "dns_or_conn", "server_error", "rate_limited"}:
        return (
            "transient_transport_failure",
            "warning",
            "Retry from another run and consider pinning or adding an independent gateway before changing the canonical URI.",
        )
    return (
        "unclassified_error",
        "error",
        "Inspect the recorded transport and validation errors manually.",
    )


def audit_candidate(
    candidate: dict[str, Any],
    policy: CrawlPolicy,
    max_attempts: int,
) -> dict[str, Any]:
    canonical = str(candidate["canonical_url"])
    loader = NetworkLoader(None, policy)
    try:
        transports = transport_candidates(canonical)
    except (PermanentCrawlError, RetryableCrawlError) as exc:
        validation = None
        errors = [
            {
                "attempt": 0,
                "retryable": bool(exc.retryable),
                "error_class": exc.error_class,
                "error": str(exc),
                "network_requests": exc.request_count,
            }
        ]
        probes: list[dict[str, Any]] = []
    else:
        probes = [_probe_transport(loader, transport) for transport in transports]
        validation, errors = _validate(loader, canonical, max_attempts)

    classification, severity, recommendation = _classification(
        canonical, probes, validation, errors
    )
    return {
        "canonical_url": canonical,
        "scheme": urllib.parse.urlsplit(canonical).scheme,
        "classification": classification,
        "severity": severity,
        "recommendation": recommendation,
        "raw_urls": sorted(candidate["raw_urls"]),
        "origins": sorted(candidate["origins"]),
        "collection_ids": sorted(candidate["collection_ids"]),
        "avatar_ids": sorted(candidate["avatar_ids"]),
        "token_ids": sorted(candidate["token_ids"]),
        "reference_count": len(candidate["references"]),
        "references": candidate["references"],
        "transport_probes": probes,
        "validation": validation,
        "validation_errors": errors,
    }


def _summarize(results: list[dict[str, Any]], invalid: list[dict[str, Any]]) -> dict[str, Any]:
    classes = Counter(result["classification"] for result in results)
    severities = Counter(result["severity"] for result in results)
    schemes = Counter(result["scheme"] for result in results)
    valid = sum(
        1
        for result in results
        if result.get("validation") and result["validation"].get("valid")
    )
    total_references = sum(int(result["reference_count"]) for result in results)
    requests = 0
    bytes_validated = 0
    for result in results:
        for probe in result.get("transport_probes") or []:
            requests += int(probe.get("network_requests") or 0)
        validation = result.get("validation") or {}
        requests += int(validation.get("network_requests") or 0)
        for error in result.get("validation_errors") or []:
            requests += int(error.get("network_requests") or 0)
        if validation.get("valid"):
            bytes_validated += int(validation.get("observed_length") or 0)
    return {
        "unique_concrete_links": len(results),
        "raw_references": total_references,
        "valid_vrm_links": valid,
        "broken_or_unverified_links": len(results) - valid,
        "invalid_uri_references": len(invalid),
        "classification_counts": dict(sorted(classes.items())),
        "severity_counts": dict(sorted(severities.items())),
        "scheme_counts": dict(sorted(schemes.items())),
        "network_requests_observed": requests,
        "validated_bytes": bytes_validated,
    }


def _collection_summary(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        collection_ids = result.get("collection_ids") or ["<unbound>"]
        for collection_id in collection_ids:
            buckets[str(collection_id)].append(result)
    out: list[dict[str, Any]] = []
    for collection_id, items in sorted(buckets.items()):
        counts = Counter(item["classification"] for item in items)
        healthy = sum(
            1
            for item in items
            if item["classification"] in {"healthy", "healthy_with_transport_degradation"}
        )
        out.append(
            {
                "collection_id": collection_id,
                "unique_links": len(items),
                "healthy_links": healthy,
                "problem_links": len(items) - healthy,
                "classification_counts": dict(sorted(counts.items())),
            }
        )
    return out


def _truncate(value: str, limit: int = 96) -> str:
    text = value.replace("|", "\\|").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# VRM link audit",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Catalog snapshot: `{report.get('snapshot_id') or 'unknown'}`",
        f"Commit: `{report.get('commit_sha') or 'unknown'}`",
        "",
        "## Outcome",
        "",
        f"- Unique concrete VRM links: **{summary['unique_concrete_links']}**",
        f"- Raw references across DB and JSON artifacts: **{summary['raw_references']}**",
        f"- Valid VRM binaries: **{summary['valid_vrm_links']}**",
        f"- Broken or unverified links: **{summary['broken_or_unverified_links']}**",
        f"- Invalid URI references: **{summary['invalid_uri_references']}**",
        f"- Full validated bytes: **{summary['validated_bytes']:,}**",
        "",
        "## Classification",
        "",
        "| Classification | Links |",
        "|---|---:|",
    ]
    for name, count in summary["classification_counts"].items():
        lines.append(f"| `{name}` | {count} |")

    lines.extend(
        [
            "",
            "## Collection coverage",
            "",
            "| Collection | Links | Healthy | Problems |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in report["collections"]:
        lines.append(
            f"| `{item['collection_id']}` | {item['unique_links']} | "
            f"{item['healthy_links']} | {item['problem_links']} |"
        )

    problems = [
        item
        for item in report["results"]
        if item["classification"] not in {"healthy"}
    ]
    lines.extend(
        [
            "",
            "## Links requiring attention",
            "",
            "| Severity | Classification | Collection | Canonical URL | Primary error or note |",
            "|---|---|---|---|---|",
        ]
    )
    for item in problems:
        validation = item.get("validation") or {}
        error = str(validation.get("error") or "")
        if not error and item.get("validation_errors"):
            error = str(item["validation_errors"][-1].get("error") or "")
        if not error and item["classification"] == "healthy_with_transport_degradation":
            failed = [
                probe
                for probe in item.get("transport_probes") or []
                if not probe.get("ok")
            ]
            error = "; ".join(
                f"{urllib.parse.urlsplit(str(probe.get('transport_url') or '')).netloc}: "
                f"{probe.get('error_class')}"
                for probe in failed
            )
        lines.append(
            f"| {item['severity']} | `{item['classification']}` | "
            f"`{','.join(item.get('collection_ids') or ['unbound'])}` | "
            f"`{_truncate(item['canonical_url'], 110)}` | {_truncate(error or item['recommendation'])} |"
        )

    if report["invalid_references"]:
        lines.extend(
            [
                "",
                "## Invalid URI references",
                "",
                "| Collection | Origin | Raw value | Error |",
                "|---|---|---|---|",
            ]
        )
        for item in report["invalid_references"]:
            lines.append(
                f"| `{item.get('collection_id') or ''}` | "
                f"`{_truncate(item['origin'], 80)}` | "
                f"`{_truncate(item['raw_url'], 100)}` | "
                f"{_truncate(item['error'])} |"
            )

    if report["templates_skipped"]:
        lines.extend(
            [
                "",
                "## Templates not directly audited",
                "",
                "Templates require concrete token IDs. They are listed here so they are not mistaken for tested links.",
                "",
                "| Collection | Origin | Template |",
                "|---|---|---|",
            ]
        )
        for item in report["templates_skipped"]:
            lines.append(
                f"| `{item.get('collection_id') or ''}` | "
                f"`{_truncate(item['origin'], 80)}` | "
                f"`{_truncate(item['template'], 110)}` |"
            )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `healthy` means the complete binary was fetched, its declared and observed lengths matched, and a VRM 0.x or VRM 1.0 extension was present.",
            "- `healthy_with_transport_degradation` means the content is valid but one or more gateway transports failed. The canonical content URI should be retained.",
            "- HTTP reachability alone is not treated as VRM proof.",
            "- This report is read-only. Canonical identity changes and link replacements require a separate reviewed patch.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=_ROOT / "data" / "vrm_index.db")
    parser.add_argument(
        "--json-report",
        type=Path,
        default=_ROOT / "data" / "vrm-link-audit.json",
    )
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=_ROOT / "docs" / "vrm-link-audit-latest.md",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-vrm-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--fail-on-broken", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"database not found: {args.db}", file=sys.stderr)
        return 2

    registry: dict[str, dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []
    templates: list[dict[str, Any]] = []
    with sqlite3.connect(str(args.db)) as conn:
        collect_from_db(conn, registry, invalid, templates)

    scanned_json = collect_from_json(
        [
            _ROOT / "static" / "data",
            _ROOT / "data" / "live_discovery_report.json",
            _ROOT / "data" / "staging_validation_report.json",
        ],
        registry,
        invalid,
        templates,
    )

    policy = CrawlPolicy(
        max_depth=0,
        request_budget=max(2_000, len(registry) * 20),
        max_tasks=max(20_000, len(registry) * 2),
        max_attempts=args.max_attempts,
        timeout=args.timeout,
        max_document_bytes=2_000_000,
        max_vrm_json_bytes=4_000_000,
        max_vrm_bytes=args.max_vrm_bytes,
        max_links_per_document=0,
    )

    results: list[dict[str, Any]] = []
    candidates = [registry[key] for key in sorted(registry)]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(audit_candidate, candidate, policy, args.max_attempts): candidate[
                "canonical_url"
            ]
            for candidate in candidates
        }
        completed = 0
        for future in as_completed(futures):
            canonical = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    {
                        "canonical_url": canonical,
                        "scheme": urllib.parse.urlsplit(canonical).scheme,
                        "classification": "internal_error",
                        "severity": "error",
                        "recommendation": "Inspect the audit implementation error.",
                        "raw_urls": sorted(registry[canonical]["raw_urls"]),
                        "origins": sorted(registry[canonical]["origins"]),
                        "collection_ids": sorted(registry[canonical]["collection_ids"]),
                        "avatar_ids": sorted(registry[canonical]["avatar_ids"]),
                        "token_ids": sorted(registry[canonical]["token_ids"]),
                        "reference_count": len(registry[canonical]["references"]),
                        "references": registry[canonical]["references"],
                        "transport_probes": [],
                        "validation": None,
                        "validation_errors": [
                            {
                                "attempt": 0,
                                "retryable": False,
                                "error_class": "internal_error",
                                "error": f"{type(exc).__name__}: {exc}",
                                "network_requests": 0,
                            }
                        ],
                    }
                )
            completed += 1
            if completed % 10 == 0 or completed == len(candidates):
                print(f"audited {completed}/{len(candidates)} unique VRM links", file=sys.stderr)

    results.sort(key=lambda item: item["canonical_url"])
    templates_unique = {
        (
            item["template"],
            item["origin"],
            item.get("collection_id"),
        ): item
        for item in templates
    }

    snapshot_id = None
    build_info_path = _ROOT / "static" / "data" / "build-info.json"
    if build_info_path.exists():
        try:
            snapshot_id = json.loads(build_info_path.read_text(encoding="utf-8")).get(
                "snapshot_id"
            )
        except (OSError, json.JSONDecodeError):
            pass

    report = {
        "schema": "vrm-link-audit-v1",
        "generated_at": utc_now(),
        "snapshot_id": snapshot_id,
        "commit_sha": os.environ.get("GITHUB_SHA") or "",
        "database": str(args.db.relative_to(_ROOT)),
        "scanned_json_files": scanned_json,
        "summary": _summarize(results, invalid),
        "collections": _collection_summary(results),
        "invalid_references": sorted(
            invalid, key=lambda item: (str(item.get("collection_id") or ""), item["raw_url"])
        ),
        "templates_skipped": sorted(
            templates_unique.values(),
            key=lambda item: (
                str(item.get("collection_id") or ""),
                item["template"],
                item["origin"],
            ),
        ),
        "results": results,
    }

    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_markdown(report, args.markdown_report)

    print(json.dumps(report["summary"], indent=2), file=sys.stderr)
    if args.fail_on_broken and report["summary"]["broken_or_unverified_links"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
