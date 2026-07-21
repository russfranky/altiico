#!/usr/bin/env python3
"""Recursive metadata scanner for VRM pointer signatures.

Many NFT metadata schemas bury the VRM file URL in non-standard fields. This
scanner walks a metadata JSON document (from a URL, local file, or stdin)
recursively and case-insensitively, looking for the known VRM-signature
patterns:

  - a URL string ending in ``.vrm``
  - a ``model/vrm`` mime type (with a sibling URL field)
  - field names: ``vrm_url``, ``vrm``, ``avatar_url``, ``model_file_url``,
    ``model_url``, ``asset``
  - ``files[].uri`` / ``files[].url`` entries pointing at a .vrm
  - ``animation_url`` ending in ``.vrm``

Each candidate URL is validated by calling
``scripts.extract_vrm_meta.fetch_vrm_meta_safe`` — a partial-GLB HTTP range
request that confirms the content is a GLB with ``extensions.VRM`` (0.x) or
``extensions.VRMC_vrm`` (1.0). A candidate is only a real VRM pointer if that
validation succeeds.

Tier A inclusion requires at least one *validated* resolvable pointer.

Usage:
    python scripts/discover_metadata_fields.py --url https://x/1.json
    python scripts/discover_metadata_fields.py --file metadata.json
    echo '{"vrm_url":"ipfs://..."}' | python scripts/discover_metadata_fields.py
    python scripts/discover_metadata_fields.py --json '{"animation_url":"https://x/y.vrm"}' --validate
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterable

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.extract_vrm_meta import fetch_vrm_meta_safe  # noqa: E402

# Field names that carry a VRM URL directly (case-insensitive match).
VRM_FIELD_NAMES = {
    "vrm_url", "vrm", "avatar_url", "model_file_url", "model_url", "asset",
    "model", "gltf", "glb",
}

# Fields whose value is a URL that should be inspected for a .vrm extension.
URL_LIKE_FIELDS = {"uri", "url", "src", "download_url", "external_url"}

# Mime types that indicate a VRM file.
VRM_MIME_TYPES = {"model/vrm", "model/gltf-binary", "application/vnd.vrm"}

VRM_EXT = ".vrm"


# --------------------------------------------------------------------------- fetch


def fetch_metadata(url: str, timeout: float = 30.0) -> Any:
    """Fetch and JSON-parse metadata from a URL (stdlib urllib)."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------- scan


def _is_vrm_url(val: str) -> bool:
    """True if the string looks like a URL ending in .vrm (query/hash stripped)."""
    if not isinstance(val, str):
        return False
    if not val:
        return False
    # Strip query string and fragment before checking extension.
    cleaned = val.split("?", 1)[0].split("#", 1)[0]
    return cleaned.lower().endswith(VRM_EXT)


def _looks_like_url(val: Any) -> bool:
    if not isinstance(val, str) or not val:
        return False
    return val.lower().startswith(("http://", "https://", "ipfs://", "ar://", "arweave://"))


def scan_metadata(
    obj: Any,
    path: str = "$",
    candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Recursively walk ``obj`` and collect VRM pointer candidates.

    Each candidate is a dict with:
      - ``path``: JSON-pointer-ish path to the field
      - ``field``: the field name where the URL was found
      - ``url``: the candidate VRM URL
      - ``reason``: why it was flagged (field_name | vrm_extension | mime |
        animation_url | files_uri)
    """
    if candidates is None:
        candidates = []

    if isinstance(obj, dict):
        # First, look for explicit mime-type siblings + URL fields.
        mime = _find_mime(obj)
        for key, val in obj.items():
            child_path = f"{path}.{key}"
            kl = key.lower()

            # 1. Known VRM field name → value is the URL.
            if kl in VRM_FIELD_NAMES and _looks_like_url(val):
                candidates.append(_cand(child_path, key, val, "field_name"))
                continue

            # 2. animation_url ending in .vrm.
            if kl == "animation_url" and _is_vrm_url(val):
                candidates.append(_cand(child_path, key, val, "animation_url"))
                continue

            # 3. A URL value ending in .vrm in any url-like field.
            if kl in URL_LIKE_FIELDS and _is_vrm_url(val):
                candidates.append(_cand(child_path, key, val, "vrm_extension"))
                continue

            # 4. A mime-type field whose value is a VRM mime, with a sibling URL.
            if kl in ("mimetype", "mime_type", "type") and isinstance(val, str) and val.lower() in VRM_MIME_TYPES:
                url_sibling = _find_url_sibling(obj, key)
                if url_sibling:
                    candidates.append(_cand(child_path, key, url_sibling, "mime"))
                continue

            # 5. A bare string value ending in .vrm (catch-all).
            if isinstance(val, str) and _is_vrm_url(val) and kl not in ("name", "description", "title"):
                candidates.append(_cand(child_path, key, val, "vrm_extension"))
                continue

            # Recurse.
            scan_metadata(val, child_path, candidates)

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            # files[].uri pattern: list of objects with uri/url fields.
            scan_metadata(item, f"{path}[{i}]", candidates)

    return candidates


def _cand(path: str, field: str, url: str, reason: str) -> dict[str, Any]:
    return {"path": path, "field": field, "url": url, "reason": reason}


def _find_mime(obj: dict) -> str | None:
    for k in ("mimetype", "mime_type", "type"):
        v = obj.get(k)
        if isinstance(v, str) and v.lower() in VRM_MIME_TYPES:
            return v
    return None


def _find_url_sibling(obj: dict, exclude_key: str) -> str | None:
    for k in URL_LIKE_FIELDS | VRM_FIELD_NAMES:
        if k == exclude_key:
            continue
        v = obj.get(k)
        if _looks_like_url(v):
            return v
    return None


# --------------------------------------------------------------------------- validate


def validate_candidates(
    candidates: list[dict[str, Any]], timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Validate each candidate URL by partial-GLB VRM extraction.

    Returns the candidates with ``valid`` (bool), ``vrm_spec``, and
    ``parse_error`` fields added.
    """
    out: list[dict[str, Any]] = []
    for c in candidates:
        result = fetch_vrm_meta_safe(c["url"], timeout=timeout)
        valid = result.get("parse_error") is None and result.get("vrm_spec") is not None
        out.append({
            **c,
            "valid": valid,
            "vrm_spec": result.get("vrm_spec"),
            "parse_error": result.get("parse_error"),
        })
    return out


# --------------------------------------------------------------------------- tier


def meets_tier_a(validated: list[dict[str, Any]]) -> bool:
    """Tier A requires at least one validated resolvable VRM pointer."""
    return any(c.get("valid") for c in validated)


# --------------------------------------------------------------------------- CLI


def _load_input(args: argparse.Namespace) -> Any:
    if args.url:
        return fetch_metadata(args.url, timeout=args.timeout)
    if args.file:
        return json.loads(Path(args.file).read_text(encoding="utf-8"))
    if args.json:
        return json.loads(args.json)
    # stdin
    return json.loads(sys.stdin.read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan NFT metadata for VRM pointer signatures and validate them."
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--url", help="metadata JSON URL to fetch")
    src.add_argument("--file", help="local metadata JSON file path")
    src.add_argument("--json", help="inline metadata JSON string")
    parser.add_argument("--validate", action="store_true",
                        help="Validate each candidate via partial-GLB VRM extraction")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="HTTP timeout per request (default 30s)")
    parser.add_argument("--quiet", action="store_true",
                        help="Only print validated candidates")
    args = parser.parse_args(argv)

    try:
        metadata = _load_input(args)
    except Exception as e:  # noqa: BLE001
        print(f"error loading metadata: {e}", file=sys.stderr)
        return 2

    candidates = scan_metadata(metadata)
    if not candidates:
        print("no VRM pointer candidates found", file=sys.stderr)
        return 1

    if args.validate:
        candidates = validate_candidates(candidates, timeout=args.timeout)

    shown = 0
    for c in candidates:
        if args.quiet and not c.get("valid"):
            continue
        line = f"{c['path']:40s}  {c['field']:20s}  {c['reason']:14s}  {c['url']}"
        if "valid" in c:
            line += f"  -> {'VALID' if c['valid'] else 'INVALID'}"
            if c.get("vrm_spec"):
                line += f" (VRM {c['vrm_spec']})"
            if c.get("parse_error"):
                line += f" [{c['parse_error']}]"
        print(line)
        shown += 1

    if args.validate:
        valid = [c for c in candidates if c.get("valid")]
        print(f"\n{len(valid)}/{len(candidates)} candidates validated as VRM"
              f"  |  Tier A: {'YES' if meets_tier_a(candidates) else 'NO'}",
              file=sys.stderr)
    else:
        print(f"\n{len(candidates)} candidate(s) found (use --validate to confirm)",
              file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
