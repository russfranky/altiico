#!/usr/bin/env python3
"""Normalize collection license terms into independent permission dimensions.

The legacy license model stored a single coarse ``license_category`` bucket
(green/yellow/red/unknown) plus free-text columns on the ``collections`` table.
This script decomposes those terms — together with embedded VRM metadata and
external license URLs — into the independent normalized dimensions defined by
migration 010 (``license_dimensions`` table), using the mappings in
``config/license-mapping.yaml`` as the single source of truth.

Precedence (highest first):
  1. Explicit project/token terms + external license URLs
     — a recognized external license URL (Creative Commons, a16z CBE) or
       explicit collection-level terms override everything below.
  2. Embedded VRM meta — the raw license/permission fields baked into the VRM
     file (migration 007), parsed per VRM spec (0.x or 1.0).
  3. Collection-level terms — the legacy ``vrm_license`` / ``commercial_use`` /
     ``allowed_user`` / ``redistribution`` columns on ``collections``.
  4. Manual curation — a pre-existing ``license_dimensions`` row whose
     ``confidence`` is ``manual``.
  5. Unknown — no signal at all. Color is ``gray``; it is NEVER promoted to
     green.

Conflict handling: when two precedence layers disagree on a dimension, the
higher-precedence value wins and is written to the dimension column, but
``conflict_flag`` is set to 1 and ``LICENSE_CONFLICT`` is appended to
``reason_codes`` (along with a detail code naming the dimension and both
values). Both raw terms are always preserved verbatim in the ``raw_*`` columns
so the conflict can be audited and re-resolved manually.

Usage:
    python scripts/normalize_licenses.py
    python scripts/normalize_licenses.py --db data/vrm_index.db
    python scripts/normalize_licenses.py --collection pixelbeasts
    python scripts/normalize_licenses.py --collection pixelbeasts --force
    python scripts/normalize_licenses.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_DB = _REPO_ROOT / "data" / "vrm_index.db"
_DEFAULT_MAPPING = _REPO_ROOT / "config" / "license-mapping.yaml"

# Dimension columns written to license_dimensions (excluding metadata columns).
_BOOL_DIMS = (
    "redistribute_original",
    "modify",
    "redistribute_modified",
    "corporate_use",
    "terminates_on_transfer",
    "hate_speech_termination",
)
_TEXT_DIMS = ("use_scope", "commercial_scope", "credit")
_ALL_DIMS = _TEXT_DIMS + _BOOL_DIMS


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------- mapping load


def load_mapping(path: str | Path = _DEFAULT_MAPPING) -> dict[str, Any]:
    """Load and validate the license-mapping.yaml config file."""
    with open(path, "r", encoding="utf-8") as fh:
        mapping = yaml.safe_load(fh)
    if not isinstance(mapping, dict):
        raise ValueError(f"license mapping {path} is not a mapping")
    for required in ("vrm_0x", "vrm_1_0", "creative_commons", "a16z_cbe", "color_rules"):
        if required not in mapping:
            raise ValueError(f"license mapping missing required section: {required}")
    return mapping


# --------------------------------------------------------------------------- dimension helpers


def _empty_dimensions() -> dict[str, Any]:
    """Return a dimensions dict with every dimension unset (None)."""
    return {k: None for k in _ALL_DIMS}


def _entry_dimensions(entry: Any) -> dict[str, Any]:
    """Extract the dimension keys from a YAML mapping entry.

    Strips ``reason_codes`` (handled separately) and coerces boolean-ish
    values to integers. Returns a dict containing only recognized dimensions.
    """
    if not isinstance(entry, dict):
        return {}
    out: dict[str, Any] = {}
    for key, val in entry.items():
        if key == "reason_codes":
            continue
        if key not in _ALL_DIMS:
            continue
        if key in _BOOL_DIMS:
            if val is None:
                continue
            if isinstance(val, bool):
                out[key] = 1 if val else 0
            else:
                out[key] = int(val)
        else:
            if val is None:
                continue
            out[key] = str(val)
    return out


def _entry_reason_codes(entry: Any) -> list[str]:
    if isinstance(entry, dict):
        rc = entry.get("reason_codes")
        if isinstance(rc, list):
            return [str(x) for x in rc]
    return []


def _resolve_license_key(key: str, mapping: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a ``section:code`` license key (e.g. ``creative_commons:CC0``).

    Returns the merged dimensions for that entry, or None if not found.
    """
    if ":" not in key:
        return None
    section, code = key.split(":", 1)
    table = mapping.get(section)
    if not isinstance(table, dict):
        return None
    entry = table.get(code)
    if entry is None:
        return None
    return _entry_dimensions(entry)


def resolve_url(url: str, mapping: dict[str, Any]) -> dict[str, Any] | None:
    """Return dimensions for a recognized external license URL, else None."""
    patterns = mapping.get("url_patterns") or []
    if not url:
        return None
    lower = url.lower()
    for pat in patterns:
        pattern = str(pat.get("pattern", "")).lower()
        if pattern and pattern in lower:
            resolved = _resolve_license_key(str(pat.get("license", "")), mapping)
            if resolved is not None:
                return resolved
    return None


# --------------------------------------------------------------------------- VRM meta mapping


def _map_vrm_0x(meta: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    """Map VRM 0.x embedded meta to dimensions.

    Field names preserve the intentional misspellings from the spec. Each
    present field contributes its entry's dimensions.
    """
    table = mapping["vrm_0x"]
    dims = _empty_dimensions()
    reason_codes: list[str] = []
    for field in ("allowedUserName", "commercialUssageName", "licenseName"):
        raw_val = meta.get(field)
        if raw_val is None or raw_val == "":
            continue
        sub = table.get(field)
        if not isinstance(sub, dict):
            continue
        entry = sub.get(str(raw_val))
        if entry is None:
            continue
        for k, v in _entry_dimensions(entry).items():
            dims[k] = v
        reason_codes.extend(_entry_reason_codes(entry))
    dims["__reason_codes__"] = reason_codes
    return dims


def _map_vrm_1_0(meta: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    """Map VRM 1.0 embedded meta to dimensions.

    Restrictive defaults from ``vrm_1_0.defaults`` are applied first, then any
    field present in the meta overrides the default. Boolean fields are looked
    up by their lowercase string form.
    """
    section = mapping["vrm_1_0"]
    defaults = section.get("defaults") or {}
    dims = _empty_dimensions()
    reason_codes: list[str] = []

    # Fields that map via a sub-table keyed by the field's value.
    value_fields = (
        "avatarPermission",
        "commercialUsage",
        "creditNotation",
        "modification",
    )
    bool_fields = ("allowRedistribution",)

    for field in value_fields + bool_fields:
        default_val = defaults.get(field)
        raw_val = meta.get(field, default_val)
        if raw_val is None:
            continue
        sub = section.get(field)
        if not isinstance(sub, dict):
            continue
        lookup_key = str(raw_val).lower() if field in bool_fields else str(raw_val)
        entry = sub.get(lookup_key)
        if entry is None:
            # Try the raw value verbatim for non-bool fields (case-sensitive).
            if field not in bool_fields:
                entry = sub.get(str(raw_val))
        if entry is None:
            continue
        for k, v in _entry_dimensions(entry).items():
            dims[k] = v
        reason_codes.extend(_entry_reason_codes(entry))

    dims["__reason_codes__"] = reason_codes
    return dims


def map_embedded_vrm_meta(
    vrm_spec: str | None,
    meta: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch to the correct VRM spec mapper based on ``vrm_spec``."""
    spec = (vrm_spec or "").strip()
    if spec.startswith("1"):
        return _map_vrm_1_0(meta, mapping)
    return _map_vrm_0x(meta, mapping)


# --------------------------------------------------------------------------- collection terms mapping


def _normalize_cc_code(code: str) -> str:
    """Normalize a Creative Commons code to canonical hyphenated form.

    VRM 0.x and the legacy ``vrm_license`` column use underscores (``CC_BY``);
    canonical Creative Commons uses hyphens (``CC-BY``).
    """
    return code.replace("_", "-").upper()


def map_collection_terms(
    terms: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Map legacy collection-level license columns to dimensions.

    ``terms`` is a dict with keys ``vrm_license``, ``commercial_use``,
    ``allowed_user``, ``redistribution`` (any may be missing/empty).
    """
    dims = _empty_dimensions()
    reason_codes: list[str] = []

    # allowed_user → use_scope
    allowed_user = (terms.get("allowed_user") or "").strip()
    if allowed_user:
        sub = mapping["vrm_0x"]["allowedUserName"]
        entry = sub.get(allowed_user)
        if entry is not None:
            for k, v in _entry_dimensions(entry).items():
                dims[k] = v
            reason_codes.extend(_entry_reason_codes(entry))

    # commercial_use → commercial_scope
    commercial = (terms.get("commercial_use") or "").strip().lower()
    if commercial == "allow":
        dims["commercial_scope"] = "personal_profit"
    elif commercial in ("disallow", "prohibited"):
        dims["commercial_scope"] = "none"
        reason_codes.append("NO_COMMERCIAL")

    # redistribution → redistribute_original
    redistribution = (terms.get("redistribution") or "").strip().lower()
    if redistribution in ("allow", "allowed"):
        dims["redistribute_original"] = 1
    elif redistribution in ("prohibited", "prohibit", "disallow"):
        dims["redistribute_original"] = 0
        reason_codes.append("REDISTRIBUTION_PROHIBITED")

    # vrm_license → creative_commons (hyphenated) or vrm_0x licenseName.
    # The legacy column is free-text (e.g. "CC0 (CBE-Public)"), so we try an
    # exact match first, then a contains/starts-with match against known codes.
    vrm_license = (terms.get("vrm_license") or "").strip()
    if vrm_license:
        cc_code = _normalize_cc_code(vrm_license)
        cc_entry = mapping["creative_commons"].get(cc_code)
        if cc_entry is None:
            cc_entry = mapping["vrm_0x"]["licenseName"].get(vrm_license)
        if cc_entry is None:
            # Fuzzy: find a known code that the normalized value starts with or
            # contains. Longer codes win so CC-BY-NC-ND beats CC-BY-NC.
            candidates = sorted(
                list(mapping["creative_commons"].keys())
                + list(mapping["vrm_0x"]["licenseName"].keys()),
                key=len,
                reverse=True,
            )
            for code in candidates:
                norm = _normalize_cc_code(code)
                if cc_code == norm or cc_code.startswith(norm + " ") or cc_code.startswith(norm + "("):
                    cc_entry = mapping["creative_commons"].get(code) or mapping["vrm_0x"][
                        "licenseName"
                    ].get(code)
                    break
        if cc_entry is not None:
            for k, v in _entry_dimensions(cc_entry).items():
                dims[k] = v
            reason_codes.extend(_entry_reason_codes(cc_entry))

    dims["__reason_codes__"] = reason_codes
    return dims


# --------------------------------------------------------------------------- merge + conflict


def _merge_layer(
    acc: dict[str, Any],
    acc_reasons: list[str],
    acc_sources: dict[str, str],
    layer: dict[str, Any],
    layer_reasons: list[str],
    source_name: str,
) -> tuple[bool, list[str]]:
    """Merge a lower-precedence ``layer`` into the accumulator ``acc``.

    Higher-precedence values already in ``acc`` win. When ``layer`` would set a
    dimension to a *different* non-null value, a conflict is recorded. Returns
    (conflict_detected, conflict_detail_codes).
    """
    conflict = False
    details: list[str] = []
    for key, val in layer.items():
        if key == "__reason_codes__":
            continue
        if val is None:
            continue
        existing = acc.get(key)
        if existing is None:
            acc[key] = val
            acc_sources[key] = source_name
        elif existing != val:
            conflict = True
            details.append(
                f"LICENSE_CONFLICT:{key}={existing}({acc_sources.get(key, '?')})"
                f"_vs_{val}({source_name})"
            )
    for rc in layer_reasons:
        if rc not in acc_reasons:
            acc_reasons.append(rc)
    return conflict, details


# --------------------------------------------------------------------------- color derivation


def _matches_value(dims: dict[str, Any], key: str, expected: Any) -> bool:
    """True if dims[key] equals expected, or is in expected (if expected is a list)."""
    actual = dims.get(key)
    if actual is None:
        return False
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def evaluate_color(dims: dict[str, Any], color_rules: list[dict[str, Any]]) -> str:
    """Return the first color whose rule matches, else 'gray'."""
    for rule in color_rules:
        if rule.get("default"):
            return rule["color"]
        matched = True
        if "conditions" in rule:
            for key, expected in rule["conditions"].items():
                if not _matches_value(dims, key, expected):
                    matched = False
                    break
        if matched and "conditions_any" in rule:
            any_match = False
            for cond in rule["conditions_any"]:
                if not isinstance(cond, dict):
                    continue
                for key, expected in cond.items():
                    if _matches_value(dims, key, expected):
                        any_match = True
                        break
                if any_match:
                    break
            matched = matched and any_match
        if matched:
            return rule["color"]
    return "gray"


# --------------------------------------------------------------------------- DB reads


def get_collection_terms(conn: sqlite3.Connection, collection_id: str) -> dict[str, Any]:
    """Read raw license columns from the collections table."""
    row = conn.execute(
        """SELECT vrm_license, commercial_use, allowed_user, redistribution,
                  license_category
           FROM collections WHERE id = ?""",
        (collection_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "vrm_license": row["vrm_license"],
        "commercial_use": row["commercial_use"],
        "allowed_user": row["allowed_user"],
        "redistribution": row["redistribution"],
        "license_category": row["license_category"],
    }


def get_embedded_vrm_meta(
    conn: sqlite3.Connection, collection_id: str
) -> list[dict[str, Any]]:
    """Return all embedded VRM meta blobs for a collection's avatars.

    Joins avatars → avatar_vrm → vrm_metadata (migration 007). A collection may
    have several avatars pointing at different VRM files; each distinct meta
    blob is returned so the caller can detect inter-avatar conflicts.
    """
    rows = conn.execute(
        """SELECT DISTINCT vm.vrm_meta_json, vm.vrm_spec
           FROM avatars a
           JOIN avatar_vrm av ON av.avatar_id = a.id
           JOIN vrm_metadata vm ON vm.source_url = av.vrm_source_url
           WHERE a.collection_id = ?
             AND vm.vrm_meta_json IS NOT NULL
             AND vm.vrm_meta_json != ''""",
        (collection_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            meta = json.loads(r["vrm_meta_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        out.append({"vrm_spec": r["vrm_spec"], "meta": meta, "raw": r["vrm_meta_json"]})
    return out


def get_external_urls(conn: sqlite3.Connection, collection_id: str) -> list[str]:
    """Collect candidate external license URLs for a collection."""
    row = conn.execute(
        """SELECT project_url, sample_metadata_url, notes, description
           FROM collections WHERE id = ?""",
        (collection_id,),
    ).fetchone()
    if row is None:
        return []
    urls: list[str] = []
    for key in ("project_url", "sample_metadata_url"):
        val = (row[key] or "").strip()
        if val:
            urls.append(val)
    # Best-effort: pull http(s) URLs out of notes/description text.
    for key in ("notes", "description"):
        text = row[key] or ""
        for token in text.split():
            if token.lower().startswith(("http://", "https://")):
                urls.append(token.rstrip(".,);"))
    # Deduplicate, preserve order.
    seen: set[str] = set()
    unique: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def get_existing_manual(
    conn: sqlite3.Connection, collection_id: str
) -> dict[str, Any] | None:
    """Return an existing manually-curated license_dimensions row, if any."""
    row = conn.execute(
        """SELECT * FROM license_dimensions
           WHERE collection_id = ? AND confidence = 'manual'""",
        (collection_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_collections(conn: sqlite3.Connection) -> list[str]:
    return [r["id"] for r in conn.execute("SELECT id FROM collections ORDER BY id")]


# --------------------------------------------------------------------------- assessment


def assess_collection(
    conn: sqlite3.Connection,
    collection_id: str,
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Build a full license_dimensions row for one collection.

    Applies the precedence chain, records conflicts, derives color, and returns
    a dict ready to be written to the table.
    """
    terms = get_collection_terms(conn, collection_id)
    embedded = get_embedded_vrm_meta(conn, collection_id)
    external_urls = get_external_urls(conn, collection_id)

    acc = _empty_dimensions()
    acc_reasons: list[str] = []
    acc_sources: dict[str, str] = {}
    conflict = False
    conflict_details: list[str] = []

    # Layer 1: external URLs (highest precedence).
    url_resolved = False
    for url in external_urls:
        resolved = resolve_url(url, mapping)
        if resolved is None:
            continue
        c, details = _merge_layer(
            acc, acc_reasons, acc_sources, resolved, [], "external_url"
        )
        conflict = conflict or c
        conflict_details.extend(details)
        url_resolved = True

    # Layer 1b: explicit collection-level terms (vrm_license etc.) are also
    # high precedence — they are curated project/token terms. We merge them
    # just below external URLs but above embedded VRM meta.
    if terms:
        coll_dims = map_collection_terms(terms, mapping)
        coll_reasons = list(coll_dims.pop("__reason_codes__", []))
        c, details = _merge_layer(
            acc, acc_reasons, acc_sources, coll_dims, coll_reasons, "collection"
        )
        conflict = conflict or c
        conflict_details.extend(details)

    # Layer 2: embedded VRM meta. If multiple avatars carry different meta,
    # each is merged in turn; disagreements between them also count as
    # conflicts.
    embedded_raw: str | None = None
    for i, entry in enumerate(embedded):
        if embedded_raw is None:
            embedded_raw = entry["raw"]
        meta_dims = map_embedded_vrm_meta(entry["vrm_spec"], entry["meta"], mapping)
        meta_reasons = list(meta_dims.pop("__reason_codes__", []))
        c, details = _merge_layer(
            acc,
            acc_reasons,
            acc_sources,
            meta_dims,
            meta_reasons,
            f"embedded[{i}]",
        )
        conflict = conflict or c
        conflict_details.extend(details)

    # Layer 3: manual curation (lowest non-unknown precedence).
    manual = get_existing_manual(conn, collection_id)
    if manual is not None:
        manual_dims = {k: manual.get(k) for k in _ALL_DIMS}
        c, details = _merge_layer(
            acc, acc_reasons, acc_sources, manual_dims, [], "manual"
        )
        conflict = conflict or c
        conflict_details.extend(details)

    # Layer 4: unknown — nothing else to add.

    # Determine confidence: highest-precedence source that contributed anything.
    if url_resolved or any(s == "external_url" for s in acc_sources.values()):
        confidence = "collection"
    elif any(s == "collection" for s in acc_sources.values()):
        confidence = "collection"
    elif embedded:
        confidence = "embedded"
    elif manual is not None:
        confidence = "manual"
    else:
        confidence = "unknown"

    # Color from dimensions. Unknown data must never be green.
    color = evaluate_color(acc, mapping["color_rules"])
    if confidence == "unknown" and color == "green":
        color = "gray"
        acc_reasons.append("NEVER_GREEN_FROM_UNKNOWN")

    # Conflict bookkeeping.
    if conflict:
        acc_reasons.append("LICENSE_CONFLICT")
        acc_reasons.extend(conflict_details)

    # De-duplicate reason codes preserving order.
    seen: set[str] = set()
    reason_codes: list[str] = []
    for rc in acc_reasons:
        if rc not in seen:
            seen.add(rc)
            reason_codes.append(rc)

    raw_collection_terms = json.dumps(terms, ensure_ascii=False) if terms else None
    raw_external_urls = json.dumps(external_urls, ensure_ascii=False) if external_urls else None

    return {
        "collection_id": collection_id,
        "raw_collection_terms": raw_collection_terms,
        "raw_embedded_vrm_meta_json": embedded_raw,
        "raw_external_urls": raw_external_urls,
        "use_scope": acc["use_scope"],
        "commercial_scope": acc["commercial_scope"],
        "credit": acc["credit"],
        "redistribute_original": acc["redistribute_original"],
        "modify": acc["modify"],
        "redistribute_modified": acc["redistribute_modified"],
        "corporate_use": acc["corporate_use"],
        "terminates_on_transfer": acc["terminates_on_transfer"],
        "hate_speech_termination": acc["hate_speech_termination"],
        "color": color,
        "reason_codes": json.dumps(reason_codes, ensure_ascii=False),
        "confidence": confidence,
        "conflict_flag": 1 if conflict else 0,
        "assessed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- write


_WRITE_COLUMNS = (
    "collection_id",
    "raw_collection_terms",
    "raw_embedded_vrm_meta_json",
    "raw_external_urls",
    "use_scope",
    "commercial_scope",
    "credit",
    "redistribute_original",
    "modify",
    "redistribute_modified",
    "corporate_use",
    "terminates_on_transfer",
    "hate_speech_termination",
    "color",
    "reason_codes",
    "confidence",
    "conflict_flag",
    "assessed_at",
)


def write_row(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    """Upsert one license_dimensions row."""
    placeholders = ",".join("?" for _ in _WRITE_COLUMNS)
    columns = ",".join(_WRITE_COLUMNS)
    conn.execute(
        f"INSERT OR REPLACE INTO license_dimensions ({columns}) VALUES ({placeholders})",
        tuple(row.get(c) for c in _WRITE_COLUMNS),
    )


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize collection license terms into permission dimensions.",
    )
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_DB),
        help=f"Path to the SQLite database (default: {_DEFAULT_DB})",
    )
    parser.add_argument(
        "--mapping",
        default=str(_DEFAULT_MAPPING),
        help=f"Path to license-mapping.yaml (default: {_DEFAULT_MAPPING})",
    )
    parser.add_argument(
        "--collection",
        help="Assess a single collection id instead of all collections",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-assess even if a non-legacy row already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print results without writing to the database",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        _log(f"Database not found: {db_path}")
        return 2

    mapping = load_mapping(args.mapping)

    conn = _connect(db_path)
    try:
        # Ensure the target table exists (idempotent with migration 010).
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='license_dimensions'"
        ).fetchone()

        if args.collection:
            collection_ids = [args.collection]
        else:
            collection_ids = list_collections(conn)

        total = len(collection_ids)
        _log(f"Assessing {total} collection(s) (dry_run={args.dry_run}, force={args.force})")

        assessed = 0
        conflicts = 0
        for cid in collection_ids:
            # Skip non-legacy existing rows unless --force.
            if not args.force:
                existing = conn.execute(
                    "SELECT confidence FROM license_dimensions WHERE collection_id = ?",
                    (cid,),
                ).fetchone()
                if existing is not None and existing["confidence"] != "legacy":
                    continue

            row = assess_collection(conn, cid, mapping)
            assessed += 1
            if row["conflict_flag"]:
                conflicts += 1
            if args.dry_run:
                print(json.dumps(row, ensure_ascii=False))
            else:
                write_row(conn, row)

        if not args.dry_run:
            conn.commit()

        _log(
            f"Done: assessed={assessed} conflicts={conflicts} "
            f"written={'0 (dry-run)' if args.dry_run else assessed}"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
