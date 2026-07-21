#!/usr/bin/env python3
"""Generate minimal synthetic VRM GLB fixtures for testing.

Creates four fixture files in tests/fixtures/vrm/:
  - vrm_0x_minimal.glb       — VRM 0.x with CC0 meta
  - vrm_1_0_minimal.glb      — VRM 1.0 with everyone/personalProfit meta
  - malformed_not_glb.glb    — 20 bytes of garbage (wrong magic)
  - no_vrm_extension.glb     — valid GLB 2.0 with no VRM extension

Run: python tests/fixtures/generate_vrm_fixtures.py
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

GLB_MAGIC = 0x46546C67
GLB_VERSION_2 = 2
JSON_CHUNK_TYPE = 0x4E4F534A
BIN_CHUNK_TYPE = 0x004E4942

FIXTURE_DIR = Path(__file__).resolve().parent / "vrm"


def build_glb(json_obj: dict, bin_data: bytes = b"") -> bytes:
    """Build a minimal GLB 2.0 file from a JSON object and optional BIN chunk."""
    json_bytes = json.dumps(json_obj, separators=(",", ":")).encode("utf-8")
    # JSON chunk padding: 0x20 (space) per GLB spec, to 4-byte alignment
    while len(json_bytes) % 4 != 0:
        json_bytes += b"\x20"
    json_chunk = struct.pack("<II", len(json_bytes), JSON_CHUNK_TYPE) + json_bytes

    bin_chunk = b""
    if bin_data:
        while len(bin_data) % 4 != 0:
            bin_data += b"\x00"
        bin_chunk = struct.pack("<II", len(bin_data), BIN_CHUNK_TYPE) + bin_data

    total_length = 12 + len(json_chunk) + len(bin_chunk)
    header = struct.pack("<III", GLB_MAGIC, GLB_VERSION_2, total_length)
    return header + json_chunk + bin_chunk


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # VRM 0.x — CC0, Everyone, Allow commercial
    vrm_0x = {
        "asset": {"version": "2.0", "generator": "superyeti-test"},
        "extensions": {
            "VRM": {
                "specVersion": "0.0",
                "meta": {
                    "title": "Test VRM 0.x",
                    "author": "TestAuthor",
                    "allowedUserName": "Everyone",
                    "violentUssageName": "Disallow",
                    "sexualUssageName": "Disallow",
                    "commercialUssageName": "Allow",
                    "licenseName": "CC0",
                    "texture": 0,
                },
            }
        },
    }
    (FIXTURE_DIR / "vrm_0x_minimal.glb").write_bytes(build_glb(vrm_0x, b"\x00" * 4))

    # VRM 1.0 — everyone, personalProfit, allowModificationRedistribution
    vrm_1_0 = {
        "asset": {"version": "2.0", "generator": "superyeti-test"},
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {
                    "name": "Test VRM 1.0",
                    "authors": ["TestAuthor"],
                    "licenseUrl": "https://vrm.dev/licenses/1.0/",
                    "avatarPermission": "everyone",
                    "commercialUsage": "personalProfit",
                    "creditNotation": "required",
                    "allowRedistribution": True,
                    "modification": "allowModificationRedistribution",
                },
            }
        },
    }
    (FIXTURE_DIR / "vrm_1_0_minimal.glb").write_bytes(build_glb(vrm_1_0, b"\x00" * 4))

    # Malformed — wrong magic number
    (FIXTURE_DIR / "malformed_not_glb.glb").write_bytes(
        struct.pack("<IIIII", 0xDEADBEEF, 2, 20, 0, 0)  # 20 bytes of garbage
    )

    # Valid GLB 2.0 but no VRM extension
    no_vrm = {
        "asset": {"version": "2.0", "generator": "superyeti-test"},
        "meshes": [],
    }
    (FIXTURE_DIR / "no_vrm_extension.glb").write_bytes(build_glb(no_vrm))

    for f in sorted(FIXTURE_DIR.glob("*.glb")):
        print(f"  {f.name}  ({f.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
