#!/usr/bin/env python3
"""
Import the Open Source Avatars registry (projects.json + per-project avatar data
files) from GitHub with commit SHA provenance.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parent
CACHE_DIR = REPO_ROOT / "data" / "cache"

OSA_GITHUB_RAW_BASE = "https://raw.githubusercontent.com/toxsam/open-source-avatars/main"
OSA_PROJECTS_URL = OSA_GITHUB_RAW_BASE + "/data/projects.json"
OSA_COMMIT_API = "https://api.github.com/repos/toxsam/open-source-avatars/commits/main"

CACHE_PROJECTS = CACHE_DIR / "opensourceavatars-projects.json"
CACHE_COMMIT_SHA = CACHE_DIR / "opensourceavatars-commit-sha.txt"
CACHE_TTL = 24 * 60 * 60  # 24 hours


def _github_get(url: str, *, parse_json: bool = True) -> Any:
    """Fetch a URL with a User-Agent header; optionally parse JSON."""
    req = urllib.request.Request(url, headers={"User-Agent": "superyeti/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    if parse_json:
        return json.loads(raw)
    return raw


def _cache_fresh(path: Path, ttl: int = CACHE_TTL) -> bool:
    """Return True if a cache file exists and is newer than ttl seconds."""
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) < ttl


def fetch_projects(use_cache: bool = True) -> tuple[list[dict], str]:
    """Fetch projects.json and the latest commit SHA, with caching.

    Returns (projects_list, commit_sha).
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if use_cache and _cache_fresh(CACHE_PROJECTS) and _cache_fresh(CACHE_COMMIT_SHA):
        projects = json.loads(CACHE_PROJECTS.read_text())
        commit_sha = CACHE_COMMIT_SHA.read_text().strip()
        return projects, commit_sha

    projects = _github_get(OSA_PROJECTS_URL)
    if not isinstance(projects, list):
        raise ValueError(f"Expected a list from projects.json, got {type(projects)}")

    commit_sha = ""
    try:
        commit_data = _github_get(OSA_COMMIT_API)
        if isinstance(commit_data, dict):
            commit_sha = commit_data.get("sha", "")
    except Exception as e:  # noqa: BLE001
        # Fall back to cached SHA if the API call fails (rate limit, etc.)
        if CACHE_COMMIT_SHA.exists():
            commit_sha = CACHE_COMMIT_SHA.read_text().strip()
        else:
            print(f"  WARN: could not fetch commit SHA: {e}")

    CACHE_PROJECTS.write_text(json.dumps(projects, indent=2))
    CACHE_COMMIT_SHA.write_text(commit_sha)
    return projects, commit_sha


def fetch_avatar_data_file(filename: str, use_cache: bool = True) -> list[dict]:
    """Fetch a per-project avatar data file and cache it.

    Returns the parsed JSON (a list of avatar entry dicts).
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Normalize filename into a safe cache path (strip directory separators).
    safe_name = filename.replace("/", "_")
    cache_path = CACHE_DIR / f"osa_{safe_name}"

    if use_cache and _cache_fresh(cache_path):
        data = json.loads(cache_path.read_text())
        return data if isinstance(data, list) else []

    url = f"{OSA_GITHUB_RAW_BASE}/data/{filename}"
    data = _github_get(url)
    if not isinstance(data, list):
        # Some files may be a dict; wrap defensively.
        if isinstance(data, dict) and "avatars" in data:
            data = data["avatars"]
        else:
            data = [data] if data else []

    cache_path.write_text(json.dumps(data, indent=2))
    return data


def derive_license_category(license: str | None) -> str:
    """Map a license string to one of: green, yellow, red, unknown."""
    if not license:
        return "unknown"
    norm = license.strip().upper().replace(" ", "")
    mapping = {
        "CC0": "green",
        "CC-BY": "green",
        "CCBY": "green",
        "CC-BY-NC": "yellow",
        "CCBYNC": "yellow",
        "CC-BY-SA": "green",
        "CCBYSA": "green",
        "CC-BY-NC-SA": "yellow",
        "CCBYNCSA": "yellow",
        "CC-BY-ND": "yellow",
        "CCBYND": "yellow",
        "MIT": "green",
        "APACHE-2.0": "green",
        "APACHE2.0": "green",
        "GPL-3.0": "green",
        "BSD-2-CLAUSE": "green",
        "BSD-3-CLAUSE": "green",
    }
    if norm in mapping:
        return mapping[norm]
    if "NC" in norm or "NONCOMMERCIAL" in norm or "ND" in norm:
        return "yellow"
    if "PROHIBITED" in norm or "NOREDISTRIBUTION" in norm or "NOREDIST" in norm:
        return "red"
    if "OTHER" in norm:
        return "unknown"
    return "unknown"


def _slugify(text: str) -> str:
    """Slugify a name into a lowercase hyphen-separated id."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "unknown"


def import_to_db(
    projects: list[dict],
    commit_sha: str,
    db_path: str,
    fetch_avatars: bool = True,
) -> dict:
    """Upsert OSA projects (and optionally avatars) into the SQLite DB.

    Returns a summary dict:
        {collections_imported, avatars_imported, errors}
    """
    summary: dict[str, Any] = {
        "collections_imported": 0,
        "avatars_imported": 0,
        "errors": [],
    }
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    notes = f"Imported from open-source-avatars commit {commit_sha[:8]}" if commit_sha else "Imported from open-source-avatars"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    for p in projects:
        try:
            name = p.get("name", "").strip()
            if not name:
                summary["errors"].append("project missing name")
                continue
            collection_id = _slugify(name)
            raw_chain = p.get("source_network") or p.get("chain") or ""
            chain = raw_chain[0] if isinstance(raw_chain, list) and raw_chain else raw_chain
            raw_contract = p.get("source_contract") or p.get("contract") or ""
            # Contracts may be a single address or a list of addresses.
            if isinstance(raw_contract, list):
                contracts = [c for c in raw_contract if c]
            elif raw_contract:
                contracts = [raw_contract]
            else:
                contracts = []
            contract = contracts[0] if contracts else ""
            license_str = p.get("license")
            license_category = derive_license_category(license_str)
            project_url = p.get("website") or p.get("project_url") or p.get("url") or p.get("opensea_url") or ""
            description = p.get("description") or ""
            image_url = ""
            avatar_data_file = p.get("avatar_data_file", "")

            # Try to grab a collection image from the first avatar entry.
            if fetch_avatars and avatar_data_file:
                try:
                    avatars = fetch_avatar_data_file(avatar_data_file)
                    if avatars:
                        first = avatars[0]
                        image_url = (
                            first.get("thumbnail_url")
                            or first.get("image_url")
                            or first.get("preview_image")
                            or ""
                        )
                except Exception as e:  # noqa: BLE001
                    summary["errors"].append(f"{name}: avatar fetch failed: {e}")

            conn.execute(
                """
                INSERT INTO collections (id, name, chain, contract, license_category,
                    vrm_license, description, project_url, image_url, source, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'opensourceavatars', ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    chain=COALESCE(NULLIF(excluded.chain, ''), collections.chain),
                    contract=COALESCE(NULLIF(excluded.contract, ''), collections.contract),
                    license_category=excluded.license_category,
                    vrm_license=COALESCE(NULLIF(excluded.vrm_license, ''), collections.vrm_license),
                    description=COALESCE(NULLIF(excluded.description, ''), collections.description),
                    project_url=COALESCE(NULLIF(excluded.project_url, ''), collections.project_url),
                    image_url=COALESCE(NULLIF(excluded.image_url, ''), collections.image_url),
                    source='opensourceavatars',
                    notes=excluded.notes
                """,
                (
                    collection_id,
                    name,
                    chain,
                    contract or None,
                    license_category,
                    license_str or None,
                    description or None,
                    project_url or None,
                    image_url or None,
                    notes,
                ),
            )
            summary["collections_imported"] += 1

            # collection_identifiers: osa_project namespace
            conn.execute(
                """
                INSERT INTO collection_identifiers
                    (collection_id, namespace, value, resolution_source, verified_at)
                VALUES (?, 'osa_project', ?, 'opensourceavatars', ?)
                ON CONFLICT(collection_id, namespace, value) DO UPDATE SET
                    resolution_source='opensourceavatars',
                    verified_at=excluded.verified_at
                """,
                (collection_id, name, now_iso),
            )

            # collection_identifiers: contract_token namespace (one row per contract)
            for c in contracts:
                conn.execute(
                    """
                    INSERT INTO collection_identifiers
                        (collection_id, namespace, value, chain, contract,
                         resolution_source, verified_at)
                    VALUES (?, 'contract_token', ?, ?, ?, 'opensourceavatars', ?)
                    ON CONFLICT(collection_id, namespace, value) DO UPDATE SET
                        chain=excluded.chain,
                        contract=excluded.contract,
                        resolution_source='opensourceavatars',
                        verified_at=excluded.verified_at
                    """,
                    (collection_id, c, chain or None, c, now_iso),
                )

            # Avatars
            if fetch_avatars and avatar_data_file:
                try:
                    avatars = fetch_avatar_data_file(avatar_data_file)
                except Exception as e:  # noqa: BLE001
                    summary["errors"].append(f"{name}: avatar fetch failed: {e}")
                    avatars = []
                for av in avatars:
                    try:
                        av_name = av.get("name", "").strip()
                        if not av_name:
                            continue
                        av_id = f"{collection_id}_{_slugify(av_name)}"
                        model_file_url = av.get("model_file_url", "") or ""
                        thumbnail_url = av.get("thumbnail_url", "") or av.get("image_url", "") or ""
                        av_format = (av.get("format") or "vrm").lower()
                        av_desc = av.get("description", "") or ""
                        metadata_json = json.dumps(av.get("metadata")) if av.get("metadata") else None
                        conn.execute(
                            """
                            INSERT INTO avatars
                                (id, collection_id, name, description, model_file_url,
                                 format, thumbnail_url, is_public, metadata_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                            ON CONFLICT(id) DO UPDATE SET
                                collection_id=excluded.collection_id,
                                name=excluded.name,
                                description=COALESCE(NULLIF(excluded.description, ''), avatars.description),
                                model_file_url=excluded.model_file_url,
                                format=excluded.format,
                                thumbnail_url=COALESCE(NULLIF(excluded.thumbnail_url, ''), avatars.thumbnail_url),
                                is_public=1,
                                metadata_json=COALESCE(excluded.metadata_json, avatars.metadata_json)
                            """,
                            (
                                av_id,
                                collection_id,
                                av_name,
                                av_desc or None,
                                model_file_url or None,
                                av_format,
                                thumbnail_url or None,
                                metadata_json,
                            ),
                        )
                        summary["avatars_imported"] += 1
                    except Exception as e:  # noqa: BLE001
                        summary["errors"].append(f"{name}/{av_name}: {e}")
        except Exception as e:  # noqa: BLE001
            summary["errors"].append(f"{p.get('name', '?')}: {e}")

    conn.commit()
    conn.close()
    return summary


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Import the Open Source Avatars registry into the superyeti DB."
    )
    parser.add_argument("--db", default=str(REPO_ROOT / "data" / "vrm_index.db"),
                        help="Path to the SQLite DB (default: data/vrm_index.db)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Force re-fetch of projects.json and commit SHA.")
    parser.add_argument("--no-avatars", action="store_true",
                        help="Skip fetching per-project avatar files; import collection-level data only.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and print what would be imported; do not write to the DB.")
    args = parser.parse_args()

    use_cache = not args.no_cache
    fetch_avatars = not args.no_avatars

    projects, commit_sha = fetch_projects(use_cache=use_cache)
    print(f"Fetched {len(projects)} projects from open-source-avatars (commit {commit_sha[:8] if commit_sha else 'unknown'})")

    if args.dry_run:
        print("\n--dry-run: would import the following collections:")
        for p in projects:
            name = p.get("name", "?")
            cid = _slugify(name)
            lic = derive_license_category(p.get("license"))
            raw_chain = p.get("source_network") or p.get("chain") or ""
            chain = raw_chain[0] if isinstance(raw_chain, list) and raw_chain else raw_chain
            raw_contract = p.get("source_contract") or p.get("contract") or ""
            if isinstance(raw_contract, list):
                contract = raw_contract[0] if raw_contract else ""
            else:
                contract = raw_contract
            adf = p.get("avatar_data_file", "")
            print(f"  {cid:40s} lic={lic:8s} chain={chain:10s} contract={contract or '-':42s} avatars={'yes' if (fetch_avatars and adf) else 'no'}")
        print(f"\nTotal: {len(projects)} collections (dry run, no DB writes)")
        return

    summary = import_to_db(projects, commit_sha, args.db, fetch_avatars=fetch_avatars)
    print(f"\nImported {summary['collections_imported']} collections, "
          f"{summary['avatars_imported']} avatars.")
    if summary["errors"]:
        print(f"Errors ({len(summary['errors'])}):")
        for e in summary["errors"]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
