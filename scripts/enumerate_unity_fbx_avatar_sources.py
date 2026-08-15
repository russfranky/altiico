#!/usr/bin/env python3
"""Enumerate public Unity FBX avatar lanes from configured GitHub sources.

This is a fail-closed bridge for surviving Unity projects such as Axolittles.
For each configured source root it:

1. resolves the requested Git ref to a commit tree;
2. exhausts the recursive Git tree and rejects truncated responses;
3. pairs every ``.fbx`` in the source root with its ``.fbx.meta`` importer file;
4. fetches the exact importer blob by SHA;
5. marks an FBX avatar-ready only when the matching importer metadata contains
   explicit Unity humanoid/avatar rig configuration; and
6. optionally merges the resulting assets into ``avatar_inventory`` in the
   generated catalog research file.

A source lane becomes ``complete`` only when the Git tree is exhaustive and
every FBX in the configured lane has matching metadata and passes the rig rule.
Anything weaker stays partial. This deliberately prefers false negatives over
counting static FBX meshes as avatars.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = ROOT / "data" / "unity_fbx_avatar_sources.json"
DEFAULT_OUTPUT = ROOT / "data" / "unity_fbx_avatar_inventory.json"
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research_merged.json"

HUMAN_NAME_RE = re.compile(r"^\s*humanName:\s*\S+", re.M)
ANIMATION_TYPE_HUMANOID_RE = re.compile(r"^\s*animationType:\s*3\s*$", re.M)
AVATAR_SETUP_RE = re.compile(r"^\s*avatarSetup:\s*([1-9]\d*)\s*$", re.M)
SKELETON_ENTRY_RE = re.compile(r"^\s*- name:\s*\S+", re.M)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_json(url: str, token: str = "", timeout: float = 30.0) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "vrm-catalog-unity-fbx-enumerator/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"GitHub response from {url} must be an object")
    return payload


def github_api(repo: str, suffix: str) -> str:
    return f"https://api.github.com/repos/{repo}/{suffix.lstrip('/')}"


def raw_url(repo: str, ref: str, path: str) -> str:
    owner, name = repo.split("/", 1)
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    return f"https://raw.githubusercontent.com/{owner}/{name}/{urllib.parse.quote(ref, safe='')}/{encoded_path}"


def blob_web_url(repo: str, ref: str, path: str) -> str:
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    return f"https://github.com/{repo}/blob/{urllib.parse.quote(ref, safe='')}/{encoded_path}"


def decode_blob(payload: dict[str, Any]) -> str:
    if payload.get("encoding") != "base64":
        raise ValueError("GitHub blob response is not base64 encoded")
    content = str(payload.get("content") or "").replace("\n", "")
    return base64.b64decode(content).decode("utf-8", errors="replace")


def rig_evidence(meta_text: str) -> dict[str, Any]:
    human_names = sorted(set(HUMAN_NAME_RE.findall(meta_text)))
    human_mapping_count = len(human_names)
    humanoid_type = bool(ANIMATION_TYPE_HUMANOID_RE.search(meta_text))
    avatar_setup = AVATAR_SETUP_RE.search(meta_text)
    skeleton_entries = len(SKELETON_ENTRY_RE.findall(meta_text))
    rigged = bool(
        human_mapping_count > 0
        or (humanoid_type and avatar_setup and skeleton_entries > 0)
    )
    return {
        "rigged": rigged,
        "humanoidMappingCount": human_mapping_count,
        "animationType3": humanoid_type,
        "avatarSetup": int(avatar_setup.group(1)) if avatar_setup else 0,
        "skeletonEntries": skeleton_entries,
    }


def resolve_tree_sha(
    repo: str,
    ref: str,
    requester: Callable[[str, str], dict[str, Any]],
    token: str,
) -> tuple[str, str]:
    commit = requester(
        github_api(repo, f"commits/{urllib.parse.quote(ref, safe='')}"), token
    )
    commit_sha = str(commit.get("sha") or "")
    tree = commit.get("commit", {}).get("tree") if isinstance(commit.get("commit"), dict) else None
    tree_sha = str(tree.get("sha") or "") if isinstance(tree, dict) else ""
    if not commit_sha or not tree_sha:
        raise ValueError(f"Unable to resolve commit/tree for {repo}@{ref}")
    return commit_sha, tree_sha


def enumerate_source(
    source: dict[str, Any],
    *,
    requester: Callable[[str, str], dict[str, Any]] = request_json,
    token: str = "",
) -> dict[str, Any]:
    collection_id = str(source.get("collection_id") or source.get("catalogId") or "").strip()
    repo = str(source.get("repo") or "").strip()
    ref = str(source.get("ref") or "main").strip()
    root = str(source.get("root") or "").strip().strip("/")
    if not collection_id or "/" not in repo or not root:
        raise ValueError("Each Unity FBX source requires collection_id, owner/repo and root")

    commit_sha, tree_sha = resolve_tree_sha(repo, ref, requester, token)
    tree_payload = requester(github_api(repo, f"git/trees/{tree_sha}?recursive=1"), token)
    rows = tree_payload.get("tree")
    if not isinstance(rows, list):
        raise ValueError(f"Git tree for {repo}@{ref} has no tree list")
    truncated = bool(tree_payload.get("truncated"))

    blobs = {
        str(row.get("path")): row
        for row in rows
        if isinstance(row, dict)
        and row.get("type") == "blob"
        and isinstance(row.get("path"), str)
    }
    prefix = root + "/"
    fbx_paths = sorted(
        path
        for path in blobs
        if path.startswith(prefix) and path.lower().endswith(".fbx")
    )

    assets: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for fbx_path in fbx_paths:
        meta_path = fbx_path + ".meta"
        meta_row = blobs.get(meta_path)
        if not isinstance(meta_row, dict) or not meta_row.get("sha"):
            failures.append({"path": fbx_path, "reason": "missing_fbx_meta"})
            continue
        try:
            meta_payload = requester(github_api(repo, f"git/blobs/{meta_row['sha']}"), token)
            meta_text = decode_blob(meta_payload)
        except Exception as exc:  # noqa: BLE001
            failures.append(
                {"path": fbx_path, "reason": "meta_fetch_error", "error": f"{type(exc).__name__}: {exc}"[:500]}
            )
            continue
        proof = rig_evidence(meta_text)
        if not proof["rigged"]:
            failures.append(
                {
                    "path": fbx_path,
                    "metaPath": meta_path,
                    "reason": "rigging_unproven",
                    "proof": proof,
                }
            )
            continue
        assets.append(
            {
                "url": raw_url(repo, commit_sha, fbx_path),
                "format": "fbx",
                "rigged": True,
                "rigging_evidence": [
                    {
                        "kind": "unity_avatar_importer_metadata",
                        "source": blob_web_url(repo, commit_sha, meta_path),
                        "note": (
                            "Matching Unity ModelImporter metadata contains explicit humanoid/avatar rig configuration: "
                            f"humanMappings={proof['humanoidMappingCount']}, animationType3={proof['animationType3']}, "
                            f"avatarSetup={proof['avatarSetup']}, skeletonEntries={proof['skeletonEntries']}."
                        ),
                    }
                ],
                "source_path": fbx_path,
                "source_blob_sha": blobs[fbx_path].get("sha"),
                "source_commit_sha": commit_sha,
            }
        )

    coverage_complete = bool(
        not truncated
        and fbx_paths
        and len(assets) == len(fbx_paths)
        and not failures
    )
    state = "complete" if coverage_complete else ("partial" if assets else "unknown")
    return {
        "collection_id": collection_id,
        "repo": repo,
        "ref": ref,
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "root": root,
        "tree_truncated": truncated,
        "fbx_files": len(fbx_paths),
        "rigged_avatar_files": len(assets),
        "coverage_complete": coverage_complete,
        "state": state,
        "assets": assets,
        "failures": failures,
        "source_evidence": source.get("evidence") if isinstance(source.get("evidence"), list) else [],
        "public": source.get("public") is True,
    }


def merge_assets(existing: Any, generated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in existing if isinstance(row, dict)] if isinstance(existing, list) else []
    by_url = {str(row.get("url") or ""): row for row in rows if row.get("url")}
    for asset in generated:
        by_url[str(asset["url"])] = asset
    return [by_url[url] for url in sorted(by_url)]


def merge_into_research(payload: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    collections = payload.get("collections")
    if not isinstance(collections, dict):
        raise ValueError("Research payload must contain a collections object")
    for result in results:
        collection_id = result["collection_id"]
        row = collections.get(collection_id)
        if not isinstance(row, dict):
            continue
        current = row.get("avatar_inventory")
        if not isinstance(current, dict):
            current = {}
        current_assets = merge_assets(current.get("assets"), result["assets"])
        current_evidence = [
            evidence
            for evidence in current.get("evidence") or []
            if isinstance(evidence, dict)
        ]
        exhaustive_evidence = {
            "kind": "exhaustive_public_github_unity_fbx_lane",
            "source": f"https://github.com/{result['repo']}/tree/{result['commit_sha']}/{result['root']}",
            "note": (
                f"Recursive Git tree was {'truncated' if result['tree_truncated'] else 'not truncated'}; "
                f"classified {result['rigged_avatar_files']} of {result['fbx_files']} FBX files in the configured avatar lane."
            ),
        }
        if exhaustive_evidence not in current_evidence:
            current_evidence.append(exhaustive_evidence)
        if result["coverage_complete"]:
            current["state"] = "complete"
            current["coverage"] = "exhaustive_public_github_unity_fbx_lane"
        elif current.get("state") not in {"complete", "not_shipped", "unrecoverable"}:
            current["state"] = "partial" if current_assets else "unknown"
            current["coverage"] = "partial_public_github_unity_fbx_lane"
        current["assets"] = current_assets
        current["evidence"] = current_evidence
        current["generated_source"] = {
            "kind": "unity_fbx_avatar_inventory",
            "repo": result["repo"],
            "commit_sha": result["commit_sha"],
            "root": result["root"],
            "coverage_complete": result["coverage_complete"],
        }
        row["avatar_inventory"] = current

        if result["public"] and result["assets"]:
            access = row.get("avatar_file_access")
            if not isinstance(access, dict) or not access.get("evidence"):
                row["avatar_file_access"] = {
                    "mode": "public",
                    "requires_ownership": False,
                    "access_url": f"https://github.com/{result['repo']}/tree/{result['commit_sha']}/{result['root']}",
                    "evidence": [exhaustive_evidence],
                }
    return payload


def run(
    sources_path: Path,
    output_path: Path,
    *,
    research_path: Path | None = None,
    write_research: bool = False,
    requester: Callable[[str, str], dict[str, Any]] = request_json,
    token: str = "",
) -> dict[str, Any]:
    sources_payload = json.loads(sources_path.read_text(encoding="utf-8"))
    sources = [row for row in sources_payload.get("sources") or [] if isinstance(row, dict)]
    results = [enumerate_source(row, requester=requester, token=token) for row in sources]
    payload = {
        "schema": "unity-fbx-avatar-inventory-v1",
        "generatedAt": now_iso(),
        "summary": {
            "sources": len(results),
            "complete": sum(row["coverage_complete"] for row in results),
            "partial": sum(row["state"] == "partial" for row in results),
            "unknown": sum(row["state"] == "unknown" for row in results),
            "fbxFiles": sum(row["fbx_files"] for row in results),
            "riggedAvatarFiles": sum(row["rigged_avatar_files"] for row in results),
            "failures": sum(len(row["failures"]) for row in results),
        },
        "sources": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if write_research:
        if research_path is None:
            raise ValueError("--write-research requires --research")
        research_payload = json.loads(research_path.read_text(encoding="utf-8"))
        merge_into_research(research_payload, results)
        research_path.write_text(
            json.dumps(research_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--write-research", action="store_true")
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN", ""))
    args = parser.parse_args()
    payload = run(
        args.sources,
        args.output,
        research_path=args.research,
        write_research=args.write_research,
        token=args.github_token,
    )
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
