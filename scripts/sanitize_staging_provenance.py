#!/usr/bin/env python3
"""Remove unproven NFT identity from collection-level Hubzz VRM samples.

`export_hubzz_staging.py` can stage a collection from a collection-level binary
VRM proof when no per-avatar proof exists. Historical `sample_metadata_url`,
`sample_nft_name`, and `sample_nft_image` fields are separate observations and
must not be attached to that VRM unless token identity was proven by the same
per-token evidence.

This sanitizer is intentionally conservative:
- only `sampleEvidence.source == "collection-validation"` is changed;
- per-avatar and recursive-crawler evidence is untouched;
- the VRM URL, validation status, size, and timestamps are preserved;
- generated sample identity becomes generic collection-level identity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "static" / "data"
STAGING_NAME = "hubzz-prealpha-staging.json"
COLLECTION_SCOPE = "collection_sample_binary"
COLLECTION_SOURCE = "collection-validation"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sanitize_sidecar(path: Path, collection_name: str) -> int:
    if not path.exists():
        return 0
    payload = load_json(path)
    changed = 0
    for avatar in payload.get("avatars") or []:
        if not isinstance(avatar, dict) or avatar.get("validationScope") != COLLECTION_SCOPE:
            continue
        desired = {
            "id": "sample",
            "tokenId": None,
            "name": f"{collection_name} sample",
            "thumbnailUrl": None,
        }
        for key, value in desired.items():
            if avatar.get(key) != value:
                avatar[key] = value
                changed += 1
    if changed:
        write_json(path, payload)
    return changed


def sanitize_staging_provenance(data_dir: Path = DEFAULT_DATA_DIR) -> dict[str, int]:
    staging_path = data_dir / STAGING_NAME
    if not staging_path.exists():
        return {"setsSanitized": 0, "sidecarFieldsSanitized": 0}

    staging = load_json(staging_path)
    sets_sanitized = 0
    sidecar_fields = 0
    for item in staging.get("sets") or []:
        if not isinstance(item, dict):
            continue
        evidence = item.get("sampleEvidence")
        if not isinstance(evidence, dict) or evidence.get("source") != COLLECTION_SOURCE:
            continue
        set_row = item.get("set") or {}
        collection_name = str(set_row.get("name") or set_row.get("slug") or "Collection")
        changed = False
        if evidence.get("tokenId") is not None:
            evidence["tokenId"] = None
            changed = True
        source_assets = item.get("sourceAssets") or {}
        relative = source_assets.get("path") if isinstance(source_assets, dict) else None
        if relative:
            sidecar_fields += sanitize_sidecar(data_dir / str(relative), collection_name)
        if changed:
            sets_sanitized += 1

    if sets_sanitized:
        write_json(staging_path, staging)
    return {
        "setsSanitized": sets_sanitized,
        "sidecarFieldsSanitized": sidecar_fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    result = sanitize_staging_provenance(args.data_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
