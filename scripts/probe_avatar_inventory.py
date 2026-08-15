#!/usr/bin/env python3
"""Probe enumerated avatar assets across VRM, GLB and FBX.

Acceptance is based on avatar usability, not filename extension alone:
- VRM: GLB 2.0 with VRM or VRMC_vrm extension.
- GLB: GLB 2.0 with at least one mesh and a skin containing joints.
- FBX: recognizable FBX bytes plus explicit evidence that the asset is rigged.

FBX rigging is not inferred from the extension because parsing arbitrary FBX
skeleton semantics robustly is outside this lightweight network probe. Research
must attach ``rigged: true`` and ``rigging_evidence`` to the asset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.crawler.fetch import (  # noqa: E402
    GLB_MAGIC,
    GLB_VERSION_2,
    JSON_CHUNK_TYPE,
    NetworkLoader,
)
from scripts.crawler.models import (  # noqa: E402
    CrawlPolicy,
    PermanentCrawlError,
    RetryableCrawlError,
)

DEFAULT_SOURCE = ROOT / "static" / "data" / "avatar-inventory.json"
DEFAULT_OUTPUT = ROOT / "data" / "avatar_inventory_probe.json"
TERMINAL_STATES = {"not_shipped", "unrecoverable"}
FBX_BINARY_MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def catalog_id(collection: dict[str, Any]) -> Any:
    return collection.get("catalogId") or collection.get("collection_id")


def terminal_state(collection: dict[str, Any]) -> str:
    explicit = collection.get("terminalResearchState")
    if explicit:
        return str(explicit).strip().lower()
    if collection.get("terminal"):
        return str(collection.get("state") or "").strip().lower()
    return ""


def metadata_complete(collection: dict[str, Any]) -> bool:
    if "metadataComplete" in collection:
        return bool(collection.get("metadataComplete"))
    return bool(collection.get("complete"))


def infer_format(url: str, explicit: Any = None) -> str:
    named = str(explicit or "").strip().lower().lstrip(".")
    if named in {"vrm", "glb", "fbx"}:
        return named
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    for fmt in ("vrm", "glb", "fbx"):
        if path.endswith(f".{fmt}"):
            return fmt
    return "unknown"


def normalize_asset(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        url = raw.strip()
        return {"url": url, "format": infer_format(url), "rigged": None, "rigging_evidence": []} if url else None
    if not isinstance(raw, dict):
        return None
    url = str(raw.get("url") or "").strip()
    if not url:
        return None
    rigging_evidence = raw.get("rigging_evidence")
    if not isinstance(rigging_evidence, list):
        rigging_evidence = []
    return {
        "url": url,
        "format": infer_format(url, raw.get("format")),
        "rigged": raw.get("rigged"),
        "rigging_evidence": [row for row in rigging_evidence if isinstance(row, dict) and row],
    }


def assets(collection: dict[str, Any]) -> list[dict[str, Any]]:
    raw = collection.get("assets")
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            normalized = normalize_asset(item)
            if normalized:
                rows.append(normalized)
    if not rows:
        urls = collection.get("urls")
        if urls is None:
            urls = collection.get("vrmUrls")
        for url in urls or []:
            normalized = normalize_asset(url)
            if normalized:
                rows.append(normalized)
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = row["url"]
        current = deduped.get(url)
        if current is None:
            deduped[url] = row
            continue
        if current.get("format") == "unknown" and row.get("format") != "unknown":
            current["format"] = row.get("format")
        if row.get("rigged") is True:
            current["rigged"] = True
        for item in row.get("rigging_evidence") or []:
            if item not in current["rigging_evidence"]:
                current["rigging_evidence"].append(item)
    return [deduped[url] for url in sorted(deduped)]


def is_fbx_prefix(body: bytes) -> bool:
    stripped = body.lstrip()
    return bool(
        body.startswith(FBX_BINARY_MAGIC)
        or stripped.startswith(b"; FBX")
        or b"FBXHeaderExtension" in body[:4096]
    )


def rigged_gltf(gltf: Any) -> bool:
    if not isinstance(gltf, dict):
        return False
    meshes = gltf.get("meshes")
    skins = gltf.get("skins")
    nodes = gltf.get("nodes")
    if not isinstance(meshes, list) or not meshes:
        return False
    if not isinstance(skins, list) or not skins:
        return False
    node_count = len(nodes) if isinstance(nodes, list) else None
    for skin in skins:
        if not isinstance(skin, dict):
            continue
        joints = skin.get("joints")
        if not isinstance(joints, list) or not joints:
            continue
        if node_count is not None and not all(
            isinstance(index, int) and 0 <= index < node_count for index in joints
        ):
            continue
        return True
    return False


def fbx_result(asset: dict[str, Any], body: bytes, requests: int) -> dict[str, Any]:
    url = asset["url"]
    if not is_fbx_prefix(body):
        return {
            "url": url,
            "status": "not_fbx",
            "validAvatar": False,
            "actualFormat": "unknown",
            "networkRequests": requests,
            "error": "file does not have a recognizable FBX header",
        }
    rigging_evidence = asset.get("rigging_evidence") or []
    rigged = asset.get("rigged") is True and bool(rigging_evidence)
    return {
        "url": url,
        "status": "valid_rigged_fbx" if rigged else "valid_fbx_rigging_unproven",
        "validAvatar": rigged,
        "validVrm": False,
        "actualFormat": "fbx",
        "rigged": rigged,
        "riggingEvidence": rigging_evidence,
        "networkRequests": requests,
        "error": None if rigged else "FBX is reachable but rigging evidence is required",
    }


def probe_asset(
    asset: dict[str, Any],
    policy: CrawlPolicy,
    *,
    loader: NetworkLoader | None = None,
) -> dict[str, Any]:
    url = asset["url"]
    format_hint = infer_format(url, asset.get("format"))
    own_loader = loader or NetworkLoader(None, policy)  # type: ignore[arg-type]
    requests = 0
    try:
        prefix_result = own_loader.fetch_range(url, 0, 4095)
        requests += int(prefix_result.network_requests or 0)
        prefix = prefix_result.body

        if format_hint == "fbx" or is_fbx_prefix(prefix):
            result = fbx_result(asset, prefix, requests)
            result["transportUrl"] = prefix_result.final_url
            return result

        if len(prefix) < 20:
            return {
                "url": url,
                "status": "invalid_glb",
                "validAvatar": False,
                "validVrm": False,
                "actualFormat": "unknown",
                "error": f"header too short: {len(prefix)}",
                "networkRequests": requests,
            }
        magic, version, total_length = struct.unpack("<III", prefix[:12])
        json_length, chunk_type = struct.unpack("<II", prefix[12:20])
        if magic != GLB_MAGIC or version != GLB_VERSION_2 or chunk_type != JSON_CHUNK_TYPE:
            return {
                "url": url,
                "status": "unsupported_or_invalid_model",
                "validAvatar": False,
                "validVrm": False,
                "actualFormat": "unknown",
                "error": "not GLB 2.0, VRM/GLB, or recognizable FBX",
                "networkRequests": requests,
            }
        if total_length < 20 or total_length > policy.max_vrm_bytes:
            return {"url": url, "status": "invalid_glb", "validAvatar": False, "validVrm": False, "actualFormat": "glb", "totalLength": total_length, "error": "declared GLB length outside policy", "networkRequests": requests}
        if json_length <= 0 or json_length > policy.max_vrm_json_bytes:
            return {"url": url, "status": "invalid_glb", "validAvatar": False, "validVrm": False, "actualFormat": "glb", "totalLength": total_length, "error": "JSON chunk length outside policy", "networkRequests": requests}
        if 20 + json_length > total_length:
            return {"url": url, "status": "invalid_glb", "validAvatar": False, "validVrm": False, "actualFormat": "glb", "totalLength": total_length, "error": "JSON chunk exceeds declared GLB length", "networkRequests": requests}

        if len(prefix) >= 20 + json_length:
            json_bytes = prefix[20 : 20 + json_length]
            transport_url = prefix_result.final_url
        else:
            json_result = own_loader.fetch_range(
                url,
                20,
                20 + json_length - 1,
                preferred_transport=prefix_result.final_url,
            )
            requests += int(json_result.network_requests or 0)
            json_bytes = json_result.body
            transport_url = json_result.final_url
        json_sha = hashlib.sha256(json_bytes).hexdigest()
        try:
            gltf = json.loads(json_bytes.decode("utf-8").rstrip("\x00 \t\r\n"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {"url": url, "status": "invalid_glb", "validAvatar": False, "validVrm": False, "actualFormat": "glb", "totalLength": total_length, "jsonChunkSha256": json_sha, "error": f"invalid GLB JSON: {exc}", "networkRequests": requests}

        extensions = gltf.get("extensions") if isinstance(gltf, dict) else None
        extensions = extensions if isinstance(extensions, dict) else {}
        if isinstance(extensions.get("VRMC_vrm"), dict):
            spec = "1.0"
        elif isinstance(extensions.get("VRM"), dict):
            spec = "0.x"
        else:
            spec = None

        if spec:
            return {
                "url": url,
                "status": "valid_vrm",
                "validAvatar": True,
                "validVrm": True,
                "actualFormat": "vrm",
                "vrmSpec": spec,
                "rigged": True,
                "riggingProof": "vrm_extension",
                "totalLength": total_length,
                "jsonChunkSha256": json_sha,
                "networkRequests": requests,
                "transportUrl": transport_url,
                "formatHint": format_hint,
                "formatMismatch": format_hint not in {"unknown", "vrm"},
                "error": None,
            }

        rigged = rigged_gltf(gltf)
        return {
            "url": url,
            "status": "valid_rigged_glb" if rigged else "valid_glb_unrigged",
            "validAvatar": rigged,
            "validVrm": False,
            "actualFormat": "glb",
            "rigged": rigged,
            "riggingProof": "gltf_skin_joints" if rigged else None,
            "totalLength": total_length,
            "jsonChunkSha256": json_sha,
            "networkRequests": requests,
            "transportUrl": transport_url,
            "formatHint": format_hint,
            "formatMismatch": format_hint not in {"unknown", "glb"},
            "error": None if rigged else "GLB has no usable skin/joint rig",
        }
    except RetryableCrawlError as exc:
        requests += int(exc.request_count or 0)
        return {"url": url, "status": "transport_error", "validAvatar": False, "validVrm": False, "retryable": True, "errorClass": exc.error_class, "error": str(exc), "networkRequests": requests}
    except PermanentCrawlError as exc:
        requests += int(exc.request_count or 0)
        return {"url": url, "status": "transport_error", "validAvatar": False, "validVrm": False, "retryable": False, "errorClass": exc.error_class, "error": str(exc), "networkRequests": requests}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status": "internal_error", "validAvatar": False, "validVrm": False, "error": f"{type(exc).__name__}: {exc}", "networkRequests": requests}


def collection_probe_summary(
    collection: dict[str, Any], probes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    terminal = terminal_state(collection)
    rows = assets(collection)
    complete = metadata_complete(collection)
    if terminal in TERMINAL_STATES:
        return {
            "catalogId": catalog_id(collection),
            "name": collection.get("name"),
            "terminalResearchState": terminal,
            "metadataComplete": complete,
            "avatarReadyComplete": complete,
            "structurallyComplete": complete,
            "urls": 0,
            "validAssetUrls": 0,
            "validVrmUrls": 0,
            "validRiggedGlbUrls": 0,
            "validRiggedFbxUrls": 0,
            "invalidUrls": [],
        }

    invalid = [row["url"] for row in rows if not (probes.get(row["url"]) or {}).get("validAvatar")]
    valid_rows = [probes.get(row["url"]) or {} for row in rows if (probes.get(row["url"]) or {}).get("validAvatar")]
    ready = bool(complete and rows and not invalid)
    return {
        "catalogId": catalog_id(collection),
        "name": collection.get("name"),
        "terminalResearchState": None,
        "metadataComplete": complete,
        "avatarReadyComplete": ready,
        "structurallyComplete": ready,
        "urls": len(rows),
        "validAssetUrls": len(valid_rows),
        "validVrmUrls": sum(row.get("actualFormat") == "vrm" for row in valid_rows),
        "validRiggedGlbUrls": sum(row.get("actualFormat") == "glb" for row in valid_rows),
        "validRiggedFbxUrls": sum(row.get("actualFormat") == "fbx" for row in valid_rows),
        "invalidUrls": invalid,
    }


def run(source_path: Path, output_path: Path, *, workers: int = 4, timeout: float = 20.0) -> dict[str, Any]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    collections = [row for row in source.get("collections") or [] if isinstance(row, dict)]
    specs: dict[str, dict[str, Any]] = {}
    for collection in collections:
        if terminal_state(collection) in TERMINAL_STATES:
            continue
        for asset in assets(collection):
            current = specs.get(asset["url"])
            if current is None:
                specs[asset["url"]] = asset
                continue
            if asset.get("rigged") is True:
                current["rigged"] = True
            for row in asset.get("rigging_evidence") or []:
                if row not in current["rigging_evidence"]:
                    current["rigging_evidence"].append(row)
    urls = sorted(specs)
    policy = CrawlPolicy(
        max_depth=0,
        request_budget=max(2_000, len(urls) * 4),
        max_tasks=max(20_000, len(urls) * 2),
        max_attempts=2,
        timeout=timeout,
        max_document_bytes=4_000_000,
        max_vrm_json_bytes=4_000_000,
        max_vrm_bytes=128 * 1024 * 1024,
        max_links_per_document=0,
    )

    probed: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(probe_asset, specs[url], policy): url for url in urls
        }
        completed = 0
        for future in as_completed(futures):
            url = futures[future]
            probed[url] = future.result()
            completed += 1
            if completed % 100 == 0 or completed == len(urls):
                print(f"probed {completed}/{len(urls)} avatar asset URLs", file=sys.stderr)

    collection_results = [collection_probe_summary(row, probed) for row in collections]
    status_counts: dict[str, int] = {}
    for result in probed.values():
        status = str(result.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    payload = {
        "schema": "avatar-inventory-structural-probe-v1",
        "generatedAt": now_iso(),
        "sourceGeneratedAt": source.get("generatedAt"),
        "policy": (
            "Every enumerated non-terminal asset must be avatar-ready: VRM extension, GLB skin/joint rig, "
            "or recognizable FBX with explicit rigging evidence."
        ),
        "summary": {
            "collections": len(collection_results),
            "avatarReadyCompleteCollections": sum(bool(row.get("avatarReadyComplete")) for row in collection_results),
            "urls": len(urls),
            "validAvatarUrls": sum(bool(row.get("validAvatar")) for row in probed.values()),
            "validVrmUrls": sum(row.get("actualFormat") == "vrm" and row.get("validAvatar") for row in probed.values()),
            "validRiggedGlbUrls": sum(row.get("actualFormat") == "glb" and row.get("validAvatar") for row in probed.values()),
            "validRiggedFbxUrls": sum(row.get("actualFormat") == "fbx" and row.get("validAvatar") for row in probed.values()),
            "statusCounts": dict(sorted(status_counts.items())),
        },
        "collections": collection_results,
        "probes": [probed[url] for url in urls],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    payload = run(args.source, args.output, workers=args.workers, timeout=args.timeout)
    print(json.dumps(payload["summary"], indent=2))
    if args.strict and payload["summary"]["avatarReadyCompleteCollections"] != payload["summary"]["collections"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
