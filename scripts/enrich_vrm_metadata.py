#!/usr/bin/env python3
"""Queue unique immutable VRM URLs from the avatars table and extract embedded
metadata via partial GLB download. Deduplicates avatars sharing one VRM file.

Reads ``model_file_url`` values from the ``avatars`` table, canonicalizes them
so that avatars pointing at the same underlying VRM file are grouped, then
extracts VRM metadata once per unique URL (using the partial-range fetcher in
``extract_vrm_meta``) and persists results in the ``vrm_metadata`` and
``avatar_vrm`` tables (migration 007).

Usage:
    python scripts/enrich_vrm_metadata.py
    python scripts/enrich_vrm_metadata.py --force
    python scripts/enrich_vrm_metadata.py --url https://example.com/model.vrm
    python scripts/enrich_vrm_metadata.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from concurrent.futures import ThreadPoolExecutor, as_completed

# Make sibling modules importable whether run as a script or a package.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))

from scripts.extract_vrm_meta import EXTRACTOR_VERSION, fetch_vrm_meta_safe  # noqa: E402

_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_DB = _REPO_ROOT / "data" / "vrm_index.db"


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- canonicalization


def canonicalize_url(url: str) -> str:
    """Normalize a VRM URL for deduplication.

    - Strip whitespace.
    - ``ipfs://`` URLs: strip whitespace after the prefix; do NOT lowercase
      the CID (IPFS CIDs are case-sensitive base58/base32 and lowercasing
      breaks content addressing).
    - ``arweave://`` URLs: lowercase the transaction id (Arweave tx ids are
      lowercase base64url by convention).
    - ``https`` URLs: lowercase the host, drop default ports (``:80``/``:443``),
      and remove trailing slashes from the path.
    """
    url = (url or "").strip()
    if not url:
        return ""

    lower_scheme = url.lower()
    if lower_scheme.startswith("ipfs://"):
        cid = url[len("ipfs://"):].strip()
        return f"ipfs://{cid}"
    if lower_scheme.startswith("arweave://"):
        tx = url[len("arweave://"):].strip()
        return f"arweave://{tx.lower()}"

    # Fall back to generic URL normalization for http(s) and anything else.
    try:
        parts = urlsplit(url)
    except ValueError:
        return url

    scheme = parts.scheme.lower()
    host = parts.hostname or ""
    host = host.lower()
    port = parts.port

    # Drop default ports.
    if port is not None:
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            port = None

    netloc = host
    if port is not None:
        netloc = f"{host}:{port}"
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo = f"{userinfo}:{parts.password}"
        netloc = f"{userinfo}@{netloc}"

    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, parts.query, parts.fragment))


# --------------------------------------------------------------------------- DB helpers


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_unique_vrm_urls(
    db_path: str | Path,
    force: bool = False,
) -> list[tuple[str, list[str]]]:
    """Return unique canonical VRM URLs and the avatar ids that reference them.

    Queries the ``avatars`` table for all non-null ``model_file_url`` values,
    canonicalizes each, groups avatar ids by canonical URL, and returns a list
    of ``(canonical_url, [avatar_id, ...])`` tuples. When *force* is False,
    URLs already present in the ``vrm_metadata`` table are skipped.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, model_file_url FROM avatars WHERE model_file_url IS NOT NULL AND model_file_url != ''"
        ).fetchall()
    finally:
        conn.close()

    groups: dict[str, list[str]] = {}
    for row in rows:
        avatar_id = row["id"]
        raw_url = row["model_file_url"]
        canon = canonicalize_url(raw_url)
        if not canon:
            continue
        groups.setdefault(canon, []).append(avatar_id)

    if not force:
        existing = set()
        if groups:
            conn = _connect(db_path)
            try:
                placeholders = ",".join("?" for _ in groups)
                cur = conn.execute(
                    f"SELECT source_url FROM vrm_metadata WHERE source_url IN ({placeholders})",
                    tuple(groups.keys()),
                )
                existing = {r["source_url"] for r in cur.fetchall()}
            finally:
                conn.close()
        for url in existing:
            groups.pop(url, None)

    # Deterministic ordering for reproducible runs.
    return sorted(groups.items(), key=lambda kv: kv[0])


# --------------------------------------------------------------------------- extraction + storage


def extract_and_store(
    url: str,
    avatar_ids: list[str],
    db_path: str | Path,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Extract VRM metadata for *url* and persist it, linking *avatar_ids*.

    Calls ``fetch_vrm_meta_safe`` (never raises), writes the result into the
    ``vrm_metadata`` table (INSERT OR REPLACE), and writes one ``avatar_vrm``
    row per avatar id linking it to the canonical URL. Returns the extraction
    result dict (augmented with ``canonical_url``).
    """
    result = fetch_vrm_meta_safe(url, timeout=timeout)

    vrm_spec = result.get("vrm_spec")
    raw_meta = result.get("raw_meta")
    parse_error = result.get("parse_error")
    total_length = result.get("total_length")
    vrm_meta_json = json.dumps(raw_meta, ensure_ascii=False) if raw_meta is not None else None

    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO vrm_metadata
                (source_url, source_etag, source_last_modified, extracted_at,
                 extractor_version, vrm_spec, vrm_meta_json, parse_error,
                 content_length, content_range)
            VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                url,
                _now_iso(),
                EXTRACTOR_VERSION,
                vrm_spec,
                vrm_meta_json,
                parse_error,
                total_length,
            ),
        )
        for avatar_id in avatar_ids:
            conn.execute(
                "INSERT OR REPLACE INTO avatar_vrm (avatar_id, vrm_source_url) VALUES (?, ?)",
                (avatar_id, url),
            )
        conn.commit()
    finally:
        conn.close()

    result["canonical_url"] = url
    return result


# --------------------------------------------------------------------------- batch


def enrich_all(
    db_path: str | Path,
    timeout: float = 30.0,
    concurrency: int = 4,
    force: bool = False,
) -> dict[str, Any]:
    """Extract metadata for every unique VRM URL in the database.

    Uses a ``ThreadPoolExecutor`` (``fetch_vrm_meta`` is synchronous /
    urllib-based) with *concurrency* workers. Prints progress to stderr and
    returns a summary dict: ``{total_urls, succeeded, failed, errors}``.
    """
    groups = get_unique_vrm_urls(db_path, force=force)
    total = len(groups)
    _log(f"Enriching {total} unique VRM URL(s) (concurrency={concurrency}, force={force})")

    succeeded = 0
    failed = 0
    errors: list[dict[str, Any]] = []

    if total == 0:
        return {"total_urls": 0, "succeeded": 0, "failed": 0, "errors": []}

    # Each worker gets its own sqlite connection via extract_and_store, so we
    # can submit all jobs up front.
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        future_to_url = {
            pool.submit(extract_and_store, url, avatar_ids, db_path, timeout): url
            for url, avatar_ids in groups
        }
        done = 0
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            done += 1
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - defensive
                failed += 1
                errors.append({"url": url, "error": str(exc)})
                _log(f"  [{done}/{total}] ERROR {url}: {exc}")
                continue

            if result.get("parse_error"):
                failed += 1
                errors.append({"url": url, "error": result["parse_error"]})
                _log(f"  [{done}/{total}] FAIL   {url}: {result['parse_error']}")
            else:
                succeeded += 1
                _log(
                    f"  [{done}/{total}] OK     {url} "
                    f"(spec={result.get('vrm_spec')}, len={result.get('total_length')})"
                )

    _log(f"Done: {succeeded} succeeded, {failed} failed, {total} total")
    return {"total_urls": total, "succeeded": succeeded, "failed": failed, "errors": errors}


# --------------------------------------------------------------------------- CLI


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Queue unique VRM URLs from the avatars table and extract embedded "
            "metadata via partial GLB download."
        )
    )
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_DB),
        help="Path to the vrm_index SQLite database (default: data/vrm_index.db)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request HTTP timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Number of concurrent extraction workers (4-8 per host recommended)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if the URL is already present in vrm_metadata",
    )
    parser.add_argument(
        "--url",
        help="Extract a single VRM URL without consulting the database",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List URLs that would be extracted, do not fetch anything",
    )
    args = parser.parse_args()

    if args.url:
        canon = canonicalize_url(args.url)
        if args.dry_run:
            _log(f"Would extract: {canon}")
            return
        _log(f"Extracting single URL: {canon}")
        result = extract_and_store(canon, [], args.db, timeout=args.timeout)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if args.dry_run:
        groups = get_unique_vrm_urls(args.db, force=args.force)
        _log(f"Would extract {len(groups)} unique VRM URL(s):")
        for url, avatar_ids in groups:
            _log(f"  {url}  ({len(avatar_ids)} avatar(s))")
        return

    summary = enrich_all(
        args.db,
        timeout=args.timeout,
        concurrency=args.concurrency,
        force=args.force,
    )
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
