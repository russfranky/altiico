#!/usr/bin/env python3

import base64
import csv
import hashlib
import json
import mimetypes
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from eth_abi import decode, encode
from eth_utils import keccak
from web3 import Web3

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

CONTRACT = Web3.to_checksum_address(
    "0x3f0785095a660fee131eebcd5aa243e529c21786"
)

# A dedicated Alchemy/Infura/QuickNode endpoint is preferable for 10k calls.
RPC_URL = os.environ.get(
    "ETH_RPC_URL",
    "https://ethereum-rpc.publicnode.com"
)

# Covers collections numbered either 0–9999 or 1–10000.
START_TOKEN = int(os.environ.get("START_TOKEN", "0"))
END_TOKEN = int(os.environ.get("END_TOKEN", "10000"))

OUTPUT = Path(os.environ.get("OUTPUT", "superyeti_archive"))
METADATA_DIR = OUTPUT / "metadata"
MODEL_DIR = OUTPUT / "models"

REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY", "0.15"))
RPC_RETRIES = 5
HTTP_RETRIES = 4

# Batch tokenURI calls via Multicall3 to avoid 10k+ individual RPC round-trips.
MULTICALL3 = Web3.to_checksum_address(
    "0xcA11bde05977b3631167028862bE2a173976CA11"
)
MULTICALL3_BATCH = int(os.environ.get("MULTICALL3_BATCH", "1000"))

IPFS_GATEWAYS = [
    "https://dweb.link/ipfs/",
    "https://ipfs.io/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
]

ARWEAVE_GATEWAY = "https://arweave.net/"

# Keys commonly used to identify NFT model files.
MODEL_KEYS = {
    "animation_url",
    "animation",
    "model",
    "model_url",
    "model_uri",
    "vrm",
    "vrm_url",
    "vrm_uri",
    "glb",
    "gltf",
    "asset",
    "asset_url",
    "download",
    "download_url",
    "three_d_url",
}

MODEL_EXTENSIONS = {
    ".vrm", ".glb", ".gltf", ".fbx", ".obj",
    ".dae", ".blend", ".usdz", ".zip"
}

ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId",
                    "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]

MULTICALL3_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "target", "type": "address"},
                    {"name": "allowFailure", "type": "bool"},
                    {"name": "callData", "type": "bytes"},
                ],
                "name": "calls",
                "type": "tuple[]",
            }
        ],
        "name": "aggregate3",
        "outputs": [
            {
                "components": [
                    {"name": "success", "type": "bool"},
                    {"name": "returnData", "type": "bytes"},
                ],
                "name": "returnData",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

TOKEN_URI_SELECTOR = keccak(text="tokenURI(uint256)")[:4]


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

session = requests.Session()
session.headers.update({
    "User-Agent": "SuperYeti-archiver/1.0",
    "Accept": "*/*",
})

# Cache fetched metadata objects so shared URIs (e.g. SuperYeti's
# dead defra.systems gateway returning the same root CID for all tokens)
# are only downloaded once.
_metadata_cache = {}


def ipfs_candidates(uri):
    """Convert an IPFS URI into several HTTP gateway candidates."""
    if not isinstance(uri, str):
        return []

    uri = uri.strip()

    if uri.startswith("ipfs://ipfs/"):
        value = uri[len("ipfs://ipfs/"):]
    elif uri.startswith("ipfs://"):
        value = uri[len("ipfs://"):]
    else:
        return [uri]

    value = value.lstrip("/")
    return [gateway + value for gateway in IPFS_GATEWAYS]


def url_candidates(uri):
    if not isinstance(uri, str):
        return []

    uri = uri.strip()

    if uri.startswith("ipfs://"):
        return ipfs_candidates(uri)

    if uri.startswith("ar://"):
        return [ARWEAVE_GATEWAY + uri[len("ar://"):]]

    if uri.startswith(("http://", "https://")):
        candidates = [uri]
        parsed = urlparse(uri)

        # SuperYeti's old defra.systems gateway is dead but its tokenURI
        # pattern embeds the IPFS path: /metadata/<cid>/asset/<token_id>.
        # Rewrite that path to an IPFS path and try public gateways.
        # Some tokens only have the root CID pinned; fall back to it.
        if parsed.netloc.lower().endswith("defra.systems"):
            path = parsed.path
            prefix = "/metadata/"
            if path.startswith(prefix):
                ipfs_path = path[len(prefix):].lstrip("/")
                candidates.extend(
                    gateway + ipfs_path for gateway in IPFS_GATEWAYS
                )
                root_cid = ipfs_path.split("/", 1)[0]
                if root_cid:
                    candidates.extend(
                        gateway + root_cid for gateway in IPFS_GATEWAYS
                    )

        # If an old gateway URL fails, also try the same CID through
        # the configured gateways.
        match = re.search(r"/ipfs/([^?#]+)", uri)
        if match:
            ipfs_path = match.group(1)
            candidates.extend(
                gateway + ipfs_path for gateway in IPFS_GATEWAYS
            )

        return list(dict.fromkeys(candidates))

    return []


def request_url(uri):
    """Fetch an HTTP/IPFS/Arweave resource with retries and fallbacks."""
    last_error = None

    for candidate in url_candidates(uri):
        for attempt in range(HTTP_RETRIES):
            try:
                response = session.get(
                    candidate,
                    timeout=(15, 180),
                    allow_redirects=True,
                )

                if response.status_code == 200:
                    return response, candidate

                last_error = RuntimeError(
                    f"HTTP {response.status_code}: {candidate}"
                )

            except requests.RequestException as exc:
                last_error = exc

            time.sleep(min(2 ** attempt, 10))

    raise RuntimeError(f"Unable to retrieve {uri}: {last_error}")


def call_with_retry(function):
    last_error = None

    for attempt in range(RPC_RETRIES):
        try:
            return function.call()
        except Exception as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 15))

    raise last_error


def _metadata_cache_key(uri):
    """Return a cache key for a metadata URI.

    For SuperYeti's defra.systems gateway the same root CID is shared
    across all token IDs, so cache by root CID rather than full URL.
    """
    if not isinstance(uri, str):
        return uri

    parsed = urlparse(uri.strip())
    if parsed.netloc.lower().endswith("defra.systems"):
        path = parsed.path
        prefix = "/metadata/"
        if path.startswith(prefix):
            return path[len(prefix):].split("/", 1)[0]

    return uri


def read_metadata(uri):
    """Read HTTP, IPFS, or base64/data-URI metadata."""
    if uri.startswith("data:application/json;base64,"):
        encoded = uri.split(",", 1)[1]
        return json.loads(base64.b64decode(encoded))

    if uri.startswith("data:application/json,"):
        encoded = uri.split(",", 1)[1]
        return json.loads(unquote(encoded))

    cache_key = _metadata_cache_key(uri)
    if cache_key in _metadata_cache:
        return _metadata_cache[cache_key]

    response, resolved_url = request_url(uri)
    metadata = response.json()
    _metadata_cache[cache_key] = metadata
    return metadata


def walk_json(value, current_key=""):
    """Yield every string value and its corresponding JSON key/path."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_json(child, str(key))

    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_json(child, f"{current_key}[{index}]")

    elif isinstance(value, str):
        yield current_key, value


def looks_like_model(key, value):
    key_lower = key.lower()
    value_lower = value.lower().split("?", 1)[0].split("#", 1)[0]

    suffix = Path(value_lower).suffix

    if suffix in MODEL_EXTENSIONS:
        return True

    if key_lower in MODEL_KEYS:
        return True

    return any(word in key_lower for word in (
        "vrm", "model", "3d", "animation", "download"
    ))


def extension_for(response, source_uri, key):
    """Determine a useful filename extension."""
    path = urlparse(source_uri).path
    suffix = Path(path).suffix.lower()

    if suffix in MODEL_EXTENSIONS:
        return suffix

    content_type = response.headers.get(
        "Content-Type", ""
    ).split(";", 1)[0].lower()

    # VRM is a GLB container and frequently arrives as octet-stream.
    if "vrm" in key.lower() or "vrm" in source_uri.lower():
        return ".vrm"

    if content_type in {
        "model/gltf-binary",
        "application/gltf-buffer",
    }:
        return ".glb"

    if content_type == "model/gltf+json":
        return ".gltf"

    guessed = mimetypes.guess_extension(content_type)
    if guessed:
        return guessed

    # GLB and VRM files begin with ASCII "glTF".
    if response.content[:4] == b"glTF":
        return ".glb"

    return ".bin"


def download_model(token_id, key, source_uri, sequence):
    response, resolved_url = request_url(source_uri)
    extension = extension_for(response, source_uri, key)

    digest = hashlib.sha256(response.content).hexdigest()

    filename = (
        f"{token_id}_{sequence:02d}_"
        f"{re.sub(r'[^A-Za-z0-9_-]+', '_', key)[:40]}"
        f"{extension}"
    )
    destination = MODEL_DIR / filename

    destination.write_bytes(response.content)

    return {
        "token_id": token_id,
        "metadata_key": key,
        "source_uri": source_uri,
        "resolved_url": resolved_url,
        "filename": str(destination),
        "size_bytes": len(response.content),
        "sha256": digest,
        "status": "downloaded",
        "error": "",
    }


# ---------------------------------------------------------------------
# Batched RPC
# ---------------------------------------------------------------------

def token_uri_calldata(token_id):
    return TOKEN_URI_SELECTOR + encode(["uint256"], [token_id])


def fetch_token_uris(web3, start, end):
    """Use Multicall3 to fetch a range of tokenURI values in one eth_call."""
    mc_contract = web3.eth.contract(address=MULTICALL3, abi=MULTICALL3_ABI)

    calls = [
        (CONTRACT, True, token_uri_calldata(token_id))
        for token_id in range(start, end + 1)
    ]

    raw = call_with_retry(mc_contract.functions.aggregate3(calls))

    results = []
    for token_id, (success, return_data) in zip(
        range(start, end + 1), raw
    ):
        if not success:
            results.append((token_id, None))
            continue

        try:
            uri = decode(["string"], return_data)[0]
            results.append((token_id, uri))
        except Exception:
            # Treat undecodable responses as reverts.
            results.append((token_id, None))

    return results


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def process_token(token_id, token_uri, writer, manifest_file):
    """Fetch metadata for a token, download any models, and log to CSV."""
    metadata_file = METADATA_DIR / f"{token_id}.json"

    try:
        if token_uri is None:
            # Nonexistent token (Multicall3 reported a revert).
            print(f"[{token_id}] nonexistent token")
            return

        print(f"[{token_id}] tokenURI: {token_uri}")
        metadata = read_metadata(token_uri)

        metadata_file.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        candidates = []
        seen = set()

        for key, value in walk_json(metadata):
            if not looks_like_model(key, value):
                continue

            if not (
                value.startswith("ipfs://")
                or value.startswith("ar://")
                or value.startswith("http://")
                or value.startswith("https://")
            ):
                continue

            if value not in seen:
                seen.add(value)
                candidates.append((key, value))

        if not candidates:
            print(f"[{token_id}] no model/VRM URL in metadata")
            writer.writerow({
                "token_id": token_id,
                "metadata_key": "",
                "source_uri": token_uri,
                "resolved_url": "",
                "filename": str(metadata_file),
                "size_bytes": metadata_file.stat().st_size,
                "sha256": "",
                "status": "metadata-only",
                "error": "No public model URL found in metadata",
            })
            manifest_file.flush()
            return

        for sequence, (key, model_uri) in enumerate(candidates, 1):
            try:
                result = download_model(
                    token_id, key, model_uri, sequence
                )
                writer.writerow(result)
                manifest_file.flush()
                print(
                    f"[{token_id}] downloaded "
                    f"{result['filename']}"
                )

            except Exception as exc:
                writer.writerow({
                    "token_id": token_id,
                    "metadata_key": key,
                    "source_uri": model_uri,
                    "resolved_url": "",
                    "filename": "",
                    "size_bytes": "",
                    "sha256": "",
                    "status": "failed",
                    "error": str(exc),
                })
                manifest_file.flush()
                print(f"[{token_id}] model failed: {exc}")

        time.sleep(REQUEST_DELAY)

    except Exception as exc:
        message = f"{token_id}\t{type(exc).__name__}: {exc}\n"
        errors_path = OUTPUT / "errors.log"
        with errors_path.open("a", encoding="utf-8") as error_file:
            error_file.write(message)

        print(f"[{token_id}] skipped: {exc}")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to: {RPC_URL}")
    web3 = Web3(Web3.HTTPProvider(
        RPC_URL,
        request_kwargs={"timeout": 60}
    ))

    if not web3.is_connected():
        raise RuntimeError(
            "Ethereum RPC connection failed. Set ETH_RPC_URL to another "
            "Ethereum mainnet provider."
        )

    if web3.eth.chain_id != 1:
        raise RuntimeError(
            f"Wrong network: chain ID {web3.eth.chain_id}; expected 1."
        )

    manifest_path = OUTPUT / "manifest.csv"
    errors_path = OUTPUT / "errors.log"

    fields = [
        "token_id",
        "metadata_key",
        "source_uri",
        "resolved_url",
        "filename",
        "size_bytes",
        "sha256",
        "status",
        "error",
    ]

    # Determine which token IDs still need work. Cached metadata files are
    # skipped, so the script is resumable.
    needed = [
        token_id
        for token_id in range(START_TOKEN, END_TOKEN + 1)
        if not (METADATA_DIR / f"{token_id}.json").exists()
    ]

    with manifest_path.open("a", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=fields)

        if manifest_file.tell() == 0:
            writer.writeheader()

        # Process tokens in Multicall3 batches to keep RPC usage minimal.
        total = len(needed)
        for batch_start in range(0, total, MULTICALL3_BATCH):
            batch_ids = needed[batch_start:batch_start + MULTICALL3_BATCH]
            if not batch_ids:
                continue

            start_id = batch_ids[0]
            end_id = batch_ids[-1]
            print(
                f"Batching tokenURIs {start_id}–{end_id} "
                f"({batch_start + 1}/{total})"
            )

            uri_results = fetch_token_uris(web3, start_id, end_id)

            for token_id, token_uri in uri_results:
                if token_id not in batch_ids:
                    continue
                process_token(token_id, token_uri, writer, manifest_file)

    print()
    print("Finished.")
    print(f"Metadata: {METADATA_DIR}")
    print(f"Models:   {MODEL_DIR}")
    print(f"Manifest: {manifest_path}")
    print(f"Errors:   {errors_path}")


if __name__ == "__main__":
    main()
