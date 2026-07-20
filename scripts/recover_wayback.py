#!/usr/bin/env python3
"""Recover the handful of SuperYeti per-token metadata snapshots archived by the Wayback Machine.

The live defra.systems endpoint is dead and only returned a generic placeholder.
Wayback captured ~17 individual /metadata/<cid>/asset/<token_id> JSON responses
from June 2021. These contain the real traits and image IPFS CIDs.
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import unquote

import requests

PROVENANCE_HASH = "QmXFtqihiEDP5sJwME5dNB3NnYk6LeiepbD4RPP1XES6Ys"
IPFS_GATEWAYS = [
    "https://dweb.link/ipfs/",
    "https://ipfs.io/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
]

# Snapshots discovered via
#   https://web.archive.org/cdx/search/cdx?url=defra.systems/*&...
ARCHIVED_SNAPSHOTS = [
    ("1234", "20210615201957"),
    ("1835", "20210615215928"),
    ("2249", "20210615221434"),
    ("3006", "20210615215726"),
    ("3074", "20210615210737"),
    ("3144", "20210615194358"),
    ("3169", "20210615202612"),
    ("3439", "20210615203446"),
    ("4234", "20210615193611"),
    ("4713", "20210615202857"),
    ("6913", "20210615222003"),
    ("7199", "20210616013649"),
    ("7200", "20210616013900"),
    ("8027", "20210615201802"),
    ("830",  "20210615200149"),
    ("8866", "20210615215008"),
    ("9729", "20210615215509"),
    ("xxxx", "20210615200513"),
]

OUTPUT = Path("superyeti_archive_wayback")
METADATA_DIR = OUTPUT / "metadata"
IMAGES_DIR = OUTPUT / "images"

session = requests.Session()
session.headers.update({
    "User-Agent": "SuperYeti-archiver/1.0 (personal recovery)",
    "Accept": "application/json,*/*",
})


def extract_cid(url):
    match = re.search(r"/ipfs/([A-Za-z0-9]+)", url)
    return match.group(1) if match else None


def fetch_url(url, retries=4):
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=(10, 60), allow_redirects=True)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as exc:
            last = str(exc)
        time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def fetch_ipfs(cid):
    for gw in IPFS_GATEWAYS:
        try:
            r = fetch_url(gw + cid)
            return r, gw + cid
        except Exception:
            continue
    raise RuntimeError(f"Could not retrieve IPFS CID {cid}")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []

    for token_id, timestamp in ARCHIVED_SNAPSHOTS:
        snapshot_url = (
            f"https://web.archive.org/web/{timestamp}/"
            f"https://defra.systems/metadata/{PROVENANCE_HASH}/asset/{token_id}"
        )
        metadata_file = METADATA_DIR / f"{token_id}.json"

        try:
            r = fetch_url(snapshot_url)
            metadata = r.json()
            metadata_file.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[{token_id}] metadata fetch failed: {exc}")
            continue

        print(f"[{token_id}] metadata saved -> {metadata_file}")

        # Check for any model/VRM-like keys in the archived metadata.
        model_refs = []
        for key, value in metadata.items():
            if isinstance(value, str) and (
                any(ext in value.lower() for ext in [".vrm", ".glb", ".gltf", ".fbx", ".zip"])
                or key.lower() in {"animation_url", "vrm", "vrm_url", "model", "model_url"}
            ):
                model_refs.append((key, value))

        image_url = metadata.get("image", "")
        image_cid = extract_cid(image_url)

        if model_refs:
            print(f"[{token_id}] FOUND MODEL REFERENCES: {model_refs}")

        if image_cid:
            try:
                img_r, resolved = fetch_ipfs(image_cid)
                ext = ".jpg" if img_r.headers.get("Content-Type", "").endswith("jpeg") else ".png"
                dest = IMAGES_DIR / f"{token_id}_{image_cid}{ext}"
                dest.write_bytes(img_r.content)
                print(f"[{token_id}] image saved -> {dest} ({len(img_r.content)} bytes)")
                manifest.append({
                    "token_id": token_id,
                    "snapshot_url": snapshot_url,
                    "metadata_file": str(metadata_file),
                    "image_cid": image_cid,
                    "image_file": str(dest),
                    "image_size": len(img_r.content),
                    "model_refs": model_refs,
                })
            except Exception as exc:
                print(f"[{token_id}] image fetch failed: {exc}")
                manifest.append({
                    "token_id": token_id,
                    "snapshot_url": snapshot_url,
                    "metadata_file": str(metadata_file),
                    "image_cid": image_cid,
                    "image_file": "",
                    "image_size": 0,
                    "model_refs": model_refs,
                    "error": str(exc),
                })
        else:
            print(f"[{token_id}] no image CID in metadata")
            manifest.append({
                "token_id": token_id,
                "snapshot_url": snapshot_url,
                "metadata_file": str(metadata_file),
                "image_cid": "",
                "image_file": "",
                "image_size": 0,
                "model_refs": model_refs,
            })

        # Be kind to the Wayback Machine.
        time.sleep(2)

    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nDone.")
    print(f"Metadata: {METADATA_DIR}")
    print(f"Images:   {IMAGES_DIR}")
    print(f"Manifest: {OUTPUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
