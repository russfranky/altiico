#!/usr/bin/env python3
"""Import the awesome-3D-avatar-collections registry from GitHub, including metadata parameter names and commit SHA for provenance."""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE / "data" / "cache"
README_CACHE = CACHE_DIR / "a3ac_readme.md"
SHA_CACHE = CACHE_DIR / "a3ac_commit_sha.txt"

A3AC_GITHUB_RAW_URL = "https://raw.githubusercontent.com/itsmetamike/awesome-3D-avatar-collections/main/README.md"
A3AC_GITHUB_API_URL = "https://api.github.com/repos/itsmetamike/awesome-3D-avatar-collections/commits/main"

CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #
def _http_get(url: str, headers: dict[str, str] | None = None) -> str:
    """Perform a GET request using urllib and return the response body as text."""
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - trusted URL
        data = resp.read()
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def _cache_fresh(path: Path) -> bool:
    """Return True if a cache file exists and is younger than CACHE_TTL_SECONDS."""
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) < CACHE_TTL_SECONDS


def fetch_readme(use_cache: bool = True) -> tuple[str, str]:
    """Fetch the A3AC README and the latest commit SHA.

    Caches results to ``data/cache/a3ac_readme.md`` and
    ``data/cache/a3ac_commit_sha.txt``. If a cache exists and is < 24 hours old
    (and ``use_cache`` is True), the cached versions are returned instead of
    hitting the network.

    Returns a ``(readme_content, commit_sha)`` tuple.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    readme_content: str | None = None
    commit_sha: str | None = None

    if use_cache and _cache_fresh(README_CACHE):
        readme_content = README_CACHE.read_text(encoding="utf-8", errors="replace")
    if use_cache and _cache_fresh(SHA_CACHE):
        commit_sha = SHA_CACHE.read_text(encoding="utf-8").strip()

    if readme_content is None:
        readme_content = _http_get(A3AC_GITHUB_RAW_URL)
        README_CACHE.write_text(readme_content, encoding="utf-8")

    if commit_sha is None or not commit_sha:
        raw = _http_get(
            A3AC_GITHUB_API_URL,
            headers={"Accept": "application/vnd.github+json"},
        )
        try:
            payload = json.loads(raw)
            commit_sha = payload.get("sha", "")
        except (json.JSONDecodeError, AttributeError):
            commit_sha = ""
        if commit_sha:
            SHA_CACHE.write_text(commit_sha, encoding="utf-8")

    return readme_content, commit_sha


# --------------------------------------------------------------------------- #
# Parsing (logic reused from parse_a3ac.py)
# --------------------------------------------------------------------------- #
def _extract_link(cell: str) -> dict | None:
    """Extract the first markdown link ``[text](url)`` from a cell."""
    m = re.search(r"\[([^\]]*)\]\(([^)]+)\)", cell)
    if m:
        return {"text": m.group(1), "url": m.group(2)}
    return None


def _extract_image(cell: str) -> str | None:
    """Extract an image URL from a markdown image cell ``![alt](url)``."""
    m = re.search(r"!\[[^\]]*\]\(([^)]+)\)", cell)
    return m.group(1) if m else None


def _extract_contract(cell: str) -> str | None:
    """Extract a 0x-prefixed 40-hex contract address from a cell."""
    m = re.search(r"0x[0-9a-fA-F]{40}", cell)
    return m.group(0) if m else None


def _extract_vrm_param(cell: str) -> str | None:
    """Extract the VRM metadata parameter name (e.g. ``vrm_url``, ``avatar_url``)."""
    if "No metadata" in cell or "N/A" in cell or "No Token" in cell:
        return None
    params: list[str] = []
    for m in re.finditer(r"`([^`]+)`", cell):
        params.append(m.group(1))
    if not params:
        for m in re.finditer(r"(?:VRM|GLB):\s*(\S+)", cell):
            params.append(m.group(1))
    return params[0] if params else None


def parse_table(readme_content: str) -> list[dict]:
    """Parse the A3AC markdown table into a list of row dicts.

    Each dict contains: ``name``, ``project_url``, ``image_url``, ``contract``,
    ``chain``, ``vrm_param``, ``sample_metadata_url``.
    """
    rows: list[dict] = []
    for line in readme_content.split("\n"):
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        # Skip the header row.
        if "Creator" in line and "Contract" in line:
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 6:
            continue
        creator_cell, contract_cell, metadata_cell, param_cell, preview_cell, vrm_cell = cells[:6]

        creator = _extract_link(creator_cell)
        contract = _extract_contract(contract_cell)
        metadata = _extract_link(metadata_cell)
        preview = _extract_image(preview_cell)
        vrm_param = _extract_vrm_param(param_cell)

        rows.append(
            {
                "name": creator["text"] if creator else "",
                "project_url": creator["url"] if creator else "",
                "image_url": preview,
                "contract": contract,
                "chain": "ethereum",
                "vrm_param": vrm_param,
                "sample_metadata_url": metadata["url"] if metadata else "",
                "has_vrm": "✔" in vrm_cell,
                "param_raw": param_cell,
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# DB import
# --------------------------------------------------------------------------- #
def _slugify(name: str) -> str:
    """Turn a collection name into a URL-safe slug id."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def import_to_db(entries: list[dict], commit_sha: str, db_path: str) -> dict:
    """Upsert parsed A3AC entries into ``collections`` and ``collection_identifiers``.

    Returns a summary dict: ``{"imported": N, "updated": N, "errors": [...]}``.
    """
    summary: dict = {"imported": 0, "updated": 0, "errors": []}
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    notes = f"Imported from awesome-3D-avatar-collections commit {commit_sha[:8]}"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for idx, entry in enumerate(entries):
            try:
                collection_id = _slugify(entry["name"])
                existing = conn.execute(
                    "SELECT id FROM collections WHERE id=?", (collection_id,)
                ).fetchone()

                conn.execute(
                    """
                    INSERT OR REPLACE INTO collections
                        (id, name, chain, contract, vrm_param,
                         sample_metadata_url, project_url, image_url,
                         source, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'a3ac', ?)
                    """,
                    (
                        collection_id,
                        entry["name"],
                        entry["chain"],
                        entry["contract"],
                        entry["vrm_param"],
                        entry["sample_metadata_url"],
                        entry["project_url"],
                        entry["image_url"],
                        notes,
                    ),
                )

                # a3ac_row identifier (row index in the README table).
                conn.execute(
                    """
                    INSERT OR REPLACE INTO collection_identifiers
                        (collection_id, namespace, value, chain, contract,
                         verified_at, resolution_source)
                    VALUES (?, 'a3ac_row', ?, ?, ?, ?, 'a3ac')
                    """,
                    (
                        collection_id,
                        str(idx),
                        entry["chain"],
                        entry["contract"],
                        now_iso,
                    ),
                )

                # contract_token identifier (when a contract address is present).
                if entry["contract"]:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO collection_identifiers
                            (collection_id, namespace, value, chain, contract,
                             verified_at, resolution_source)
                        VALUES (?, 'contract_token', ?, ?, ?, ?, 'a3ac')
                        """,
                        (
                            collection_id,
                            entry["contract"],
                            entry["chain"],
                            entry["contract"],
                            now_iso,
                        ),
                    )

                if existing:
                    summary["updated"] += 1
                else:
                    summary["imported"] += 1
            except Exception as exc:  # pragma: no cover - defensive
                summary["errors"].append(f"{entry.get('name', '?')}: {exc}")
        conn.commit()
    finally:
        conn.close()

    return summary


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the awesome-3D-avatar-collections registry from GitHub."
    )
    parser.add_argument("--db", default=str(BASE / "data" / "vrm_index.db"), help="Path to the SQLite database.")
    parser.add_argument("--no-cache", action="store_true", help="Force re-fetch the README and commit SHA.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print without writing to the DB.")
    args = parser.parse_args()

    readme_content, commit_sha = fetch_readme(use_cache=not args.no_cache)
    print(f"A3AC commit SHA: {commit_sha or '(unknown)'}", file=sys.stderr)

    entries = parse_table(readme_content)
    print(f"Parsed {len(entries)} collections from A3AC README", file=sys.stderr)

    if args.dry_run:
        for e in entries:
            print(
                f"  {e['name']:40s} contract={e['contract'] or '-':12s} "
                f"vrm_param={e['vrm_param'] or '-'}",
                file=sys.stderr,
            )
        return

    summary = import_to_db(entries, commit_sha, args.db)
    print(
        f"Imported: {summary['imported']}  Updated: {summary['updated']}  "
        f"Errors: {len(summary['errors'])}",
        file=sys.stderr,
    )
    for err in summary["errors"]:
        print(f"  ERROR: {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
