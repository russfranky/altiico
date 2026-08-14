#!/usr/bin/env python3
"""Extract OpenPage/MML avatar asset leads without weakening VRM proof rules.

OpenPage avatar records can expose several representations of the same avatar.
This adapter preserves MML, VRM and GLB/GLTF URLs as separate evidence lanes.
MML and GLB are never promoted to VRM. Explicit ``.vrm`` URLs found directly in
an OpenPage record or referenced by an MML ``<m-character>``/``<m-model>`` tag
are emitted only as candidates for the existing binary VRM validator.

Input is intentionally generic so exports/API responses can be saved verbatim.
Accepted top-level shapes include a list of records, a single record object, or
an object containing ``records``, ``avatars``, ``items``, ``results`` or
``collections`` lists.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "openpage_asset_discovery.json"
URL_RE = re.compile(r"(?:https?|ipfs|ar)://[^\s\"'<>]+", re.I)
VRM_RE = re.compile(r"\.vrm(?:$|[?#])", re.I)
GLB_RE = re.compile(r"\.(?:glb|gltf)(?:$|[?#])", re.I)
MML_SRC_RE = re.compile(
    r"<m-(?:character|model)\b[^>]*?\bsrc\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))",
    re.I | re.S,
)
LIST_KEYS = ("records", "avatars", "items", "results", "collections")
CATALOG_ID_KEYS = ("catalogId", "catalog_id", "collection_id")
OPENPAGE_ID_KEYS = ("openpageId", "openpage_id", "avatarId", "avatar_id", "id")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def walk(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def record_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in LIST_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return [payload]


def explicit_id(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = text(record.get(key))
        if value:
            return value
    return None


def normalize_url(raw: str, base_url: str | None = None) -> str:
    value = raw.strip().rstrip(".,;)")
    if base_url and not urllib.parse.urlsplit(value).scheme:
        return urllib.parse.urljoin(base_url, value)
    return value


def classify_url(url: str, path_hint: str = "") -> str | None:
    lowered = url.lower()
    if VRM_RE.search(lowered):
        return "vrm"
    if GLB_RE.search(lowered):
        return "glb"
    if "mml" in path_hint.lower():
        return "mml"
    return None


def mml_model_urls(markup: str, base_url: str | None = None) -> list[str]:
    urls: list[str] = []
    for match in MML_SRC_RE.finditer(markup):
        raw = next((group for group in match.groups() if group is not None), "")
        value = normalize_url(raw, base_url)
        if value:
            urls.append(value)
    return sorted(set(urls))


def url_hits(value: str) -> list[str]:
    return [normalize_url(match.group(0)) for match in URL_RE.finditer(value)]


def add_hit(
    target: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    *,
    url: str,
    source: str,
    via: str,
) -> None:
    normalized = normalize_url(url)
    key = (normalized, via)
    if not normalized or key in seen:
        return
    seen.add(key)
    target.append({"url": normalized, "source": source, "via": via})


def fetch_text(url: str, timeout: float = 15.0) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "vrm-catalog-openpage-discovery/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def inspect_fetched_mml(
    payload: str,
    *,
    source_url: str,
) -> list[tuple[str, str]]:
    """Return ``(kind,url)`` references from fetched MML or JSON metadata."""
    hits: list[tuple[str, str]] = []
    for url in mml_model_urls(payload, source_url):
        kind = classify_url(url)
        if kind in {"vrm", "glb"}:
            hits.append((kind, url))
    stripped = payload.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            decoded = None
        if decoded is not None:
            for path, value in walk(decoded):
                for url in url_hits(value):
                    kind = classify_url(url, path)
                    if kind in {"vrm", "glb", "mml"}:
                        hits.append((kind, url))
                for url in mml_model_urls(value, source_url):
                    kind = classify_url(url)
                    if kind in {"vrm", "glb"}:
                        hits.append((kind, url))
    return sorted(set(hits))


def inspect_record(
    record: dict[str, Any],
    *,
    index: int = 0,
    fetch_mml: bool = False,
    fetcher: Callable[[str], str] = fetch_text,
) -> dict[str, Any]:
    catalog_id = explicit_id(record, CATALOG_ID_KEYS)
    openpage_id = explicit_id(record, OPENPAGE_ID_KEYS)
    mml: list[dict[str, Any]] = []
    vrm: list[dict[str, Any]] = []
    glb: list[dict[str, Any]] = []
    seen_mml: set[tuple[str, str]] = set()
    seen_vrm: set[tuple[str, str]] = set()
    seen_glb: set[tuple[str, str]] = set()

    for path, value in walk(record):
        for url in url_hits(value):
            kind = classify_url(url, path)
            if kind == "mml":
                add_hit(mml, seen_mml, url=url, source=path, via="openpage_record")
            elif kind == "vrm":
                add_hit(vrm, seen_vrm, url=url, source=path, via="openpage_record")
            elif kind == "glb":
                add_hit(glb, seen_glb, url=url, source=path, via="openpage_record")

        if "<m-character" in value.lower() or "<m-model" in value.lower():
            for model_url in mml_model_urls(value):
                kind = classify_url(model_url)
                if kind == "vrm":
                    add_hit(vrm, seen_vrm, url=model_url, source=path, via="mml_inline")
                elif kind == "glb":
                    add_hit(glb, seen_glb, url=model_url, source=path, via="mml_inline")

    fetch_errors: list[dict[str, str]] = []
    if fetch_mml:
        # Only HTTP(S) MML references are fetchable by this adapter. IPFS/ar URLs
        # remain preserved evidence and can be resolved by a dedicated gateway.
        for hit in list(mml):
            url = hit["url"]
            if not url.startswith(("http://", "https://")):
                continue
            try:
                body = fetcher(url)
            except Exception as exc:  # noqa: BLE001
                fetch_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"[:500]})
                continue
            for kind, model_url in inspect_fetched_mml(body, source_url=url):
                if kind == "vrm":
                    add_hit(vrm, seen_vrm, url=model_url, source=url, via="mml_fetched")
                elif kind == "glb":
                    add_hit(glb, seen_glb, url=model_url, source=url, via="mml_fetched")
                elif kind == "mml":
                    add_hit(mml, seen_mml, url=model_url, source=url, via="mml_fetched")

    return {
        "recordIndex": index,
        "catalogId": catalog_id,
        "openpageId": openpage_id,
        "mmlUrls": sorted(mml, key=lambda row: (row["url"], row["via"])),
        "vrmCandidates": sorted(vrm, key=lambda row: (row["url"], row["via"])),
        "glbUrls": sorted(glb, key=lambda row: (row["url"], row["via"])),
        "fetchErrors": fetch_errors,
    }


def load_inputs(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.extend(record_list(payload))
    return records


def build_report(
    records: list[dict[str, Any]],
    *,
    fetch_mml: bool = False,
    fetcher: Callable[[str], str] = fetch_text,
) -> dict[str, Any]:
    inspected = [
        inspect_record(row, index=index, fetch_mml=fetch_mml, fetcher=fetcher)
        for index, row in enumerate(records)
    ]
    return {
        "schema": "openpage-asset-discovery-v1",
        "generatedAt": now_iso(),
        "policy": (
            "OpenPage MML and GLB are separate runtime representations and never prove VRM. "
            "Explicit .vrm URLs are discovery candidates only until the catalog binary validator "
            "confirms VRM structure and the collection inventory is proven exhaustive."
        ),
        "summary": {
            "records": len(inspected),
            "recordsWithCatalogId": sum(bool(row["catalogId"]) for row in inspected),
            "recordsWithMml": sum(bool(row["mmlUrls"]) for row in inspected),
            "recordsWithVrmCandidates": sum(bool(row["vrmCandidates"]) for row in inspected),
            "recordsWithGlb": sum(bool(row["glbUrls"]) for row in inspected),
            "uniqueVrmCandidates": len(
                {hit["url"] for row in inspected for hit in row["vrmCandidates"]}
            ),
            "fetchErrors": sum(len(row["fetchErrors"]) for row in inspected),
        },
        "records": inspected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        required=True,
        help="JSON export/API response; repeat for multiple inputs",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--fetch-mml",
        action="store_true",
        help="Fetch HTTP(S) MML URLs and inspect m-character/m-model src references",
    )
    args = parser.parse_args()
    report = build_report(load_inputs(args.input), fetch_mml=args.fetch_mml)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
