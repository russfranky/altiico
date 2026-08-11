#!/usr/bin/env python3
"""Verify one coherent, secret-free catalog artifact snapshot."""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.catalog_snapshot import compute_snapshot_id  # noqa: E402

_SECRET_PATTERNS = (
    re.compile(r"\bvcp_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\b(?:sk|pk)_[A-Za-z0-9_-]{24,}\b"),
)
_CONTRACT_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"artifact is not an object: {path}")
    return value


def _norm_contract(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = _CONTRACT_RE.search(value)
    return match.group(0).lower() if match else None


def _canonical_contracts(conn: sqlite3.Connection) -> tuple[dict[str, str | None], dict[str, str]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, contract, opensea_slug FROM collections").fetchall()
    contracts: dict[str, str | None] = {}
    slug_to_id: dict[str, str] = {}
    for row in rows:
        cid = str(row["id"])
        contract = _norm_contract(row["contract"])
        if contract is None:
            found = conn.execute(
                """
                SELECT address FROM contracts
                WHERE collection_id=?
                ORDER BY is_primary DESC, rowid ASC
                LIMIT 1
                """,
                (cid,),
            ).fetchone()
            contract = _norm_contract(found["address"]) if found else None
        contracts[cid] = contract
        slug = str(row["opensea_slug"] or "").strip()
        if slug and slug not in slug_to_id:
            slug_to_id[slug] = cid
    return contracts, slug_to_id


def _check_contract(
    errors: list[str],
    source: str,
    collection_id: str,
    observed: Any,
    canonical: dict[str, str | None],
) -> None:
    expected = canonical.get(collection_id)
    actual = _norm_contract(observed)
    if expected and actual and expected != actual:
        errors.append(
            f"{source}: {collection_id} contract {actual} != canonical {expected}"
        )


def verify(db_path: Path, data_dir: Path, static_dir: Path) -> list[str]:
    errors: list[str] = []
    conn = sqlite3.connect(str(db_path))
    try:
        expected_snapshot = compute_snapshot_id(conn)
        canonical, slug_to_id = _canonical_contracts(conn)
    finally:
        conn.close()

    build_info = _load(data_dir / "build-info.json")
    collections_path = data_dir / str((build_info.get("files") or {}).get("collections") or "")
    collections = _load(collections_path)
    manifest = _load(data_dir / "avatar-manifest-v1.json")
    registry = _load(data_dir / "avatars-registry.json")
    staging = _load(data_dir / "hubzz-prealpha-staging.json")

    snapshots = {
        "database": expected_snapshot,
        "build-info": build_info.get("snapshot_id"),
        "collections": collections.get("snapshot_id"),
        "avatar-manifest": manifest.get("snapshot_id"),
        "avatars-registry": registry.get("snapshot_id"),
        "hubzz-staging": staging.get("snapshotId"),
    }
    for name, value in snapshots.items():
        if value != expected_snapshot:
            errors.append(
                f"snapshot mismatch: {name}={value!r}, expected {expected_snapshot!r}"
            )

    for item in collections.get("collections") or []:
        if isinstance(item, dict) and item.get("id"):
            _check_contract(errors, "collections", str(item["id"]), item.get("contract"), canonical)

    for item in registry.get("collections") or []:
        if isinstance(item, dict) and item.get("slug"):
            _check_contract(errors, "avatars-registry", str(item["slug"]), item.get("contract"), canonical)

    for item in staging.get("sets") or []:
        if not isinstance(item, dict):
            continue
        record = item.get("set") or {}
        slug = str(record.get("slug") or "")
        if slug:
            _check_contract(errors, "hubzz-staging", slug, record.get("contract"), canonical)
        source = item.get("sourceAssets") or {}
        sidecar_rel = source.get("path")
        if sidecar_rel:
            sidecar = _load(data_dir / str(sidecar_rel))
            if sidecar.get("snapshotId") != expected_snapshot:
                errors.append(
                    f"sidecar snapshot mismatch: {sidecar_rel}={sidecar.get('snapshotId')!r}"
                )

    for item in manifest.get("collections") or []:
        if not isinstance(item, dict):
            continue
        identifiers = item.get("identifiers") or {}
        slug = identifiers.get("opensea_slug")
        cid = slug_to_id.get(str(slug)) if slug else None
        if cid is None and isinstance(item.get("id"), str) and item["id"] in canonical:
            cid = item["id"]
        if cid:
            _check_contract(errors, "avatar-manifest", cid, identifiers.get("contract"), canonical)
            _check_contract(errors, "avatar-manifest-id", cid, item.get("id"), canonical)

    for path in static_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".js", ".html", ".css"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"secret-like value in static artifact: {path.relative_to(_REPO_ROOT)}")
        for env_name in ("OPENSEA_API_KEY", "VERCEL_TOKEN"):
            value = os.environ.get(env_name)
            if value and len(value) >= 12 and value in text:
                errors.append(
                    f"exact {env_name} value leaked into {path.relative_to(_REPO_ROOT)}"
                )

    market_as_of = build_info.get("market_data_as_of")
    if isinstance(market_as_of, str):
        try:
            parsed = datetime.fromisoformat(market_as_of.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600
            print(f"market_data_age_hours={age_hours:.1f}")
        except ValueError:
            errors.append(f"invalid market_data_as_of timestamp: {market_as_of!r}")

    if not errors:
        print(f"snapshot={expected_snapshot}")
        print("catalog consistency: OK")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=_REPO_ROOT / "data" / "vrm_index.db")
    parser.add_argument("--data-dir", type=Path, default=_REPO_ROOT / "static" / "data")
    parser.add_argument("--static-dir", type=Path, default=_REPO_ROOT / "static")
    args = parser.parse_args()
    errors = verify(args.db, args.data_dir, args.static_dir)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
