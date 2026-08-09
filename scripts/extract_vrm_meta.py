"""Partial-GLB VRM metadata extractor.

The VRM metadata is in the first JSON chunk of the GLB file, so a two-range
HTTP request avoids downloading meshes and textures. Python stdlib only — no
Node.js or aiohttp dependency.
"""

import argparse
import json
import struct
import sys
import urllib.request
from typing import Any, Dict, Optional


GLB_MAGIC = 0x46546C67
GLB_VERSION_2 = 2
JSON_CHUNK_TYPE = 0x4E4F534A
EXTRACTOR_VERSION = "1.0.0"


def get_range(url: str, start: int, end: int, timeout: float = 30.0) -> bytes:
    """Fetch bytes [start, end] inclusive from url via HTTP Range request.

    Uses urllib.request (stdlib). Follows redirects. Accepts both 206 (Partial
    Content) and 200 (full response if server ignores Range). If 200 and the
    response is larger than the requested range, returns only the requested bytes.
    Raises RuntimeError on other HTTP errors.
    """
    headers = {
        "Range": f"bytes={start}-{end}",
        "Accept-Encoding": "identity",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - user-supplied URL
        status = getattr(resp, "status", None) or resp.getcode()
        data = resp.read()

    if status in (206, 200):
        requested_len = end - start + 1
        if status == 200 and len(data) > requested_len:
            return data[start : start + requested_len]
        return data

    raise RuntimeError(f"HTTP request failed with status {status}")


def parse_glb_header(header: bytes) -> tuple[int, int, int, int]:
    """Parse a 20-byte GLB header + first chunk header.

    Returns (magic, version, total_length, json_length, chunk_type).
    """
    if len(header) < 20:
        raise ValueError(f"Header too short: {len(header)} bytes, need 20")
    magic, version, total_length = struct.unpack("<III", header[0:12])
    json_length, chunk_type = struct.unpack("<II", header[12:20])
    return magic, version, total_length, json_length, chunk_type


def extract_vrm_from_gltf(gltf: dict, source_url: str, total_length: int) -> Dict[str, Any]:
    """Extract VRM metadata from a parsed glTF JSON dict.

    Returns a dict with keys: vrm_spec, raw_meta, total_length, source_url.
    Raises ValueError if the glTF has no VRM extension.
    """
    extensions: Optional[Dict[str, Any]] = gltf.get("extensions")
    if not extensions:
        raise ValueError("GLB has no VRM extension")

    # VRM 1.0
    vrmc = extensions.get("VRMC_vrm")
    if vrmc is not None:
        meta = vrmc.get("meta")
        return {
            "vrm_spec": "1.0",
            "raw_meta": meta,
            "total_length": total_length,
            "source_url": source_url,
        }

    # VRM 0.x
    vrm0 = extensions.get("VRM")
    if vrm0 is not None:
        meta = vrm0.get("meta")
        return {
            "vrm_spec": "0.x",
            "raw_meta": meta,
            "total_length": total_length,
            "source_url": source_url,
        }

    raise ValueError("GLB has no VRM extension")


def summarize_meta(meta: Dict[str, Any], vrm_spec: Optional[str]) -> Dict[str, Any]:
    """Reduce a raw VRM meta block to a spec-aware, flat summary.

    VRM 0.x and VRM 1.0 use different field names for the same concepts
    (e.g. 0.x ``author`` / ``licenseName`` vs 1.0 ``authors[]`` / ``licenseUrl``),
    so the summary must branch on ``vrm_spec``. See docs/vrm-ecosystem.md.
    """
    if vrm_spec == "1.0":
        authors = meta.get("authors")
        author = ", ".join(authors) if isinstance(authors, list) else authors
        return {
            "title": meta.get("name"),
            "author": author,
            "license": meta.get("licenseUrl"),
            "allowed_user": meta.get("avatarPermission"),
            "commercial": meta.get("commercialUsage"),
            "sexual": meta.get("allowExcessivelySexualUsage"),
            "violent": meta.get("allowExcessivelyViolentUsage"),
            "credit": meta.get("creditNotation"),
            "modification": meta.get("modification"),
            "redistribution": meta.get("allowRedistribution"),
        }
    # VRM 0.x (field names carry the intentional spec misspellings).
    return {
        "title": meta.get("title"),
        "author": meta.get("author"),
        "license": meta.get("licenseName"),
        "allowed_user": meta.get("allowedUserName"),
        "commercial": meta.get("commercialUssageName"),
        "sexual": meta.get("sexualUssageName"),
        "violent": meta.get("violentUssageName"),
        "other_license_url": meta.get("otherLicenseUrl"),
    }


def parse_glb(data: bytes, source_url: str = "<bytes>") -> Dict[str, Any]:
    """Parse a complete GLB byte buffer and extract VRM metadata.

    This is the testable core of the extractor — no HTTP involved. Tests can
    read a fixture file and call this directly.
    """
    magic, version, total_length, json_length, chunk_type = parse_glb_header(data[:20])

    if magic != GLB_MAGIC:
        raise ValueError(
            f"Not a GLB file: magic 0x{magic:08X} != expected 0x{GLB_MAGIC:08X}"
        )
    if version != GLB_VERSION_2:
        raise ValueError(
            f"Unsupported GLB version {version}, expected {GLB_VERSION_2}"
        )
    if chunk_type != JSON_CHUNK_TYPE:
        raise ValueError(
            f"First chunk is not JSON: type 0x{chunk_type:08X} != expected 0x{JSON_CHUNK_TYPE:08X}"
        )

    json_bytes = data[20 : 20 + json_length]
    gltf = json.loads(json_bytes.decode("utf-8").rstrip("\x00 \t\r\n"))
    return extract_vrm_from_gltf(gltf, source_url, total_length)


def fetch_vrm_meta(url: str, timeout: float = 30.0, max_full_bytes: int = 2_000_000) -> Dict[str, Any]:
    """Fetch VRM metadata from a GLB file using two HTTP range requests.

    Returns a dict with keys: vrm_spec, raw_meta, total_length, source_url.
    Raises ValueError if the file is not a valid GLB or has no VRM extension.
    """
    # Step 1: fetch the GLB header + first chunk header (bytes 0-19).
    header = get_range(url, 0, 19, timeout=timeout)

    magic, version, total_length, json_length, chunk_type = parse_glb_header(header)

    if magic != GLB_MAGIC:
        raise ValueError(
            f"Not a GLB file: magic 0x{magic:08X} != expected 0x{GLB_MAGIC:08X}"
        )
    if version != GLB_VERSION_2:
        raise ValueError(
            f"Unsupported GLB version {version}, expected {GLB_VERSION_2}"
        )
    if chunk_type != JSON_CHUNK_TYPE:
        raise ValueError(
            f"First chunk is not JSON: type 0x{chunk_type:08X} != expected 0x{JSON_CHUNK_TYPE:08X}"
        )

    # Step 2: fetch the JSON chunk (bytes 20 to 20+json_length-1).
    json_bytes = get_range(url, 20, 20 + json_length - 1, timeout=timeout)
    gltf = json.loads(json_bytes.decode("utf-8"))
    return extract_vrm_from_gltf(gltf, url, total_length)


def fetch_vrm_meta_safe(url: str, **kwargs: Any) -> Dict[str, Any]:
    """Never-raising wrapper around fetch_vrm_meta.

    On any exception, returns a dict with parse_error set and other fields nulled.
    """
    try:
        return fetch_vrm_meta(url, **kwargs)
    except Exception as e:  # noqa: BLE001 - intentional broad catch
        return {
            "source_url": url,
            "vrm_spec": None,
            "raw_meta": None,
            "parse_error": str(e),
            "total_length": None,
        }


def main() -> None:
    """CLI entry point: fetch VRM metadata from a URL and print as JSON."""
    parser = argparse.ArgumentParser(
        description="Extract VRM metadata from a GLB file via partial HTTP range requests."
    )
    parser.add_argument("url", help="The VRM file URL")
    parser.add_argument("--timeout", type=float, default=30, help="HTTP timeout in seconds (default 30)")
    parser.add_argument("--raw", action="store_true", help="Print full raw_meta JSON, not just a summary")
    args = parser.parse_args()

    result = fetch_vrm_meta_safe(args.url, timeout=args.timeout)

    if args.raw:
        output: Dict[str, Any] = result
    else:
        meta = result.get("raw_meta")
        summary: Dict[str, Any] = {
            "source_url": result.get("source_url"),
            "vrm_spec": result.get("vrm_spec"),
            "total_length": result.get("total_length"),
            "parse_error": result.get("parse_error"),
        }
        if isinstance(meta, dict):
            summary.update(summarize_meta(meta, result.get("vrm_spec")))
        output = summary

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
