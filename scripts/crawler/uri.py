"""URI canonicalization and recursive metadata link discovery.

The crawler keeps decentralized-storage identity separate from transport. An
IPFS object remains ``ipfs://CID/path`` in the evidence graph even when it is
fetched through several HTTPS gateways.
"""

from __future__ import annotations

import base64
import json
import posixpath
import re
import urllib.parse
from typing import Any, Iterable

from scripts.crawler.models import DiscoveredLink, PermanentCrawlError


IPFS_GATEWAY_HOSTS = {
    "ipfs.io",
    "gateway.ipfs.io",
    "dweb.link",
    "nftstorage.link",
    "w3s.link",
    "gateway.pinata.cloud",
    "cloudflare-ipfs.com",
}
IPFS_GATEWAYS = (
    "https://ipfs.io/ipfs/",
    "https://dweb.link/ipfs/",
    "https://nftstorage.link/ipfs/",
)
ARWEAVE_GATEWAY = "https://arweave.net/"

VRM_FIELD_NAMES = {
    "vrm",
    "vrm_url",
    "avatar_url",
    "model_file_url",
    "model_url",
    "asset",
    "gltf",
    "glb",
}
METADATA_FIELD_NAMES = {
    "metadata",
    "metadata_url",
    "metadata_uri",
    "token_uri",
    "tokenuri",
    "manifest",
    "manifest_url",
    "json_url",
}
URL_FIELD_NAMES = {
    "uri",
    "url",
    "src",
    "href",
    "download_url",
    "animation_url",
    "external_url",
    *VRM_FIELD_NAMES,
    *METADATA_FIELD_NAMES,
}
VRM_MIME_TYPES = {
    "model/vrm",
    "application/vrm",
    "application/vnd.vrm",
}
GLTF_MIME_TYPES = {
    "model/gltf-binary",
    "model/gltf+json",
}
JSON_MIME_TYPES = {
    "application/json",
    "application/ld+json",
    "text/json",
}

_DATA_JSON_RE = re.compile(r"^data:(?:application/(?:ld\+)?json|text/json)", re.I)
_WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")


def _strip_default_port(parts: urllib.parse.SplitResult) -> str:
    host = parts.hostname or ""
    if not host:
        return ""
    port = parts.port
    if port is None:
        return host
    if (parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443):
        return host
    return f"{host}:{port}"


def _gateway_to_ipfs(url: str) -> str | None:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()

    # Path gateways: https://gateway.example/ipfs/CID/path
    if host in IPFS_GATEWAY_HOSTS or host.endswith(".mypinata.cloud"):
        marker = "/ipfs/"
        idx = parts.path.find(marker)
        if idx < 0:
            return None
        suffix = parts.path[idx + len(marker):].lstrip("/")
        if not suffix:
            return None
    else:
        # Subdomain gateways: https://CID.ipfs.gateway.example/path
        identifier = None
        for gateway_host in sorted(IPFS_GATEWAY_HOSTS, key=len, reverse=True):
            marker = f".ipfs.{gateway_host}"
            if host.endswith(marker):
                identifier = host[:-len(marker)]
                break
        if not identifier:
            return None

        raw_path = parts.path.lstrip("/")
        # Legacy rows sometimes repeat /ipfs/CID/ even though the CID
        # is already present in the gateway subdomain.
        duplicate = f"ipfs/{identifier}"
        if raw_path == duplicate:
            raw_path = ""
        elif raw_path.startswith(duplicate + "/"):
            raw_path = raw_path[len(duplicate) + 1:]
        suffix = identifier + (f"/{raw_path}" if raw_path else "")

    out = f"ipfs://{suffix}"
    if parts.query:
        out += f"?{parts.query}"
    return out

def _gateway_to_arweave(url: str) -> str | None:
    parts = urllib.parse.urlsplit(url)
    if (parts.hostname or "").lower() != "arweave.net":
        return None
    suffix = parts.path.lstrip("/")
    if not suffix:
        return None
    out = f"ar://{suffix}"
    if parts.query:
        out += f"?{parts.query}"
    return out


def canonicalize_uri(value: str) -> str:
    """Return a stable fetch identity without changing case-sensitive paths."""
    if not isinstance(value, str):
        raise PermanentCrawlError("URI must be a string", error_class="invalid_uri")
    raw = value.strip()
    if not raw:
        raise PermanentCrawlError("URI is empty", error_class="invalid_uri")
    if "\x00" in raw or _WINDOWS_DRIVE_RE.match(raw):
        raise PermanentCrawlError("local paths are not crawlable", error_class="blocked_uri")

    if _DATA_JSON_RE.match(raw):
        # Data URIs are immutable and self-identifying. Preserve bytes exactly.
        return raw

    if raw.lower().startswith("arweave://"):
        raw = "ar://" + raw[len("arweave://"):]

    gateway = _gateway_to_ipfs(raw)
    if gateway:
        raw = gateway
    else:
        gateway = _gateway_to_arweave(raw)
        if gateway:
            raw = gateway

    parts = urllib.parse.urlsplit(raw)
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https", "ipfs", "ipns", "ar"}:
        raise PermanentCrawlError(
            f"unsupported URI scheme: {parts.scheme or '<none>'}",
            error_class="unsupported_scheme",
        )
    if parts.username or parts.password:
        raise PermanentCrawlError("credential-bearing URLs are blocked", error_class="blocked_uri")

    if scheme in {"http", "https"}:
        netloc = _strip_default_port(parts).lower()
        if not netloc:
            raise PermanentCrawlError("HTTP URI has no host", error_class="invalid_uri")
        path = parts.path or "/"
        return urllib.parse.urlunsplit((scheme, netloc, path, parts.query, ""))

    # ipfs/ipns/ar use the authority/path as a case-sensitive content identity.
    authority = parts.netloc
    path = parts.path
    if not authority:
        # Accept ipfs:CID/path as input and normalize to ipfs://CID/path.
        compact = path.lstrip("/")
        authority, sep, rest = compact.partition("/")
        path = f"/{rest}" if sep else ""
    if scheme == "ipfs" and authority.lower() == "ipfs":
        compact = path.lstrip("/")
        authority, sep, rest = compact.partition("/")
        path = f"/{rest}" if sep else ""
    if not authority:
        raise PermanentCrawlError(f"{scheme} URI has no identifier", error_class="invalid_uri")
    return urllib.parse.urlunsplit((scheme, authority, path, parts.query, ""))


def resolve_uri(base: str, value: str) -> str:
    """Resolve a relative metadata link against HTTP, IPFS, IPNS, or Arweave."""
    raw = value.strip()
    if not raw:
        raise PermanentCrawlError("empty relative URI", error_class="invalid_uri")
    if _DATA_JSON_RE.match(raw) or urllib.parse.urlsplit(raw).scheme:
        return canonicalize_uri(raw)

    base_canonical = canonicalize_uri(base)
    parts = urllib.parse.urlsplit(base_canonical)
    if parts.scheme in {"http", "https"}:
        return canonicalize_uri(urllib.parse.urljoin(base_canonical, raw))

    # urllib.urljoin does not consistently treat custom schemes as hierarchical.
    query = ""
    fragmentless = raw.split("#", 1)[0]
    if "?" in fragmentless:
        relative_path, query = fragmentless.split("?", 1)
    else:
        relative_path = fragmentless
    if relative_path.startswith("/"):
        joined_path = posixpath.normpath(relative_path)
    else:
        parent = posixpath.dirname(parts.path or "/")
        joined_path = posixpath.normpath(posixpath.join(parent, relative_path))
    if not joined_path.startswith("/"):
        joined_path = "/" + joined_path
    return canonicalize_uri(
        urllib.parse.urlunsplit((parts.scheme, parts.netloc, joined_path, query, ""))
    )


def transport_candidates(canonical_url: str) -> list[str]:
    """Return ordered HTTPS transport URLs for one canonical resource."""
    canonical = canonicalize_uri(canonical_url)
    parts = urllib.parse.urlsplit(canonical)
    if parts.scheme in {"http", "https"}:
        return [canonical]
    if parts.scheme == "ipfs":
        suffix = parts.netloc + parts.path
        if parts.query:
            suffix += f"?{parts.query}"
        return [gateway + suffix for gateway in IPFS_GATEWAYS]
    if parts.scheme == "ipns":
        suffix = parts.netloc + parts.path
        if parts.query:
            suffix += f"?{parts.query}"
        return [f"https://ipfs.io/ipns/{suffix}", f"https://dweb.link/ipns/{suffix}"]
    if parts.scheme == "ar":
        suffix = parts.netloc + parts.path
        if parts.query:
            suffix += f"?{parts.query}"
        return [ARWEAVE_GATEWAY + suffix]
    if parts.scheme == "data":
        return [canonical]
    raise PermanentCrawlError("no transport for URI", error_class="unsupported_scheme")


def decode_data_json(uri: str, max_bytes: int) -> bytes:
    """Decode a JSON data URI with either base64 or percent encoding."""
    if not _DATA_JSON_RE.match(uri):
        raise PermanentCrawlError("not a JSON data URI", error_class="invalid_data_uri")
    try:
        header, payload = uri.split(",", 1)
    except ValueError as exc:
        raise PermanentCrawlError("malformed data URI", error_class="invalid_data_uri") from exc
    try:
        if ";base64" in header.lower():
            body = base64.b64decode(payload, validate=True)
        else:
            body = urllib.parse.unquote_to_bytes(payload)
    except (ValueError, base64.binascii.Error) as exc:
        raise PermanentCrawlError("invalid data URI payload", error_class="invalid_data_uri") from exc
    if len(body) > max_bytes:
        raise PermanentCrawlError("data URI exceeds document cap", error_class="document_too_large")
    return body


def _looks_absolute(value: str) -> bool:
    lower = value.strip().lower()
    return lower.startswith(("http://", "https://", "ipfs://", "ipns://", "ar://", "arweave://", "data:"))


def _looks_relative_url(value: str) -> bool:
    value = value.strip()
    if not value or value.startswith(('#', '@')):
        return False
    if any(ch.isspace() for ch in value):
        return False
    return value.startswith(("./", "../", "/")) or "/" in value or "." in value


def _path_extension(url: str) -> str:
    if _DATA_JSON_RE.match(url):
        return ".json"
    path = urllib.parse.urlsplit(url).path.lower()
    basename = posixpath.basename(path)
    if "." not in basename:
        return ""
    return "." + basename.rsplit(".", 1)[-1]


def _mime_from_dict(obj: dict[str, Any]) -> str:
    for key in ("mimetype", "mime_type", "mime", "type", "content_type"):
        value = obj.get(key)
        if isinstance(value, str):
            return value.lower().split(";", 1)[0].strip()
    return ""


def _classify(field: str, url: str, mime: str) -> tuple[str | None, str, float]:
    field_l = field.lower()
    ext = _path_extension(url)
    mime_l = mime.lower().split(";", 1)[0].strip()

    if field_l in VRM_FIELD_NAMES:
        return "asset", "vrm_field", 0.95
    if field_l == "animation_url" and ext == ".vrm":
        return "asset", "animation_vrm", 0.98
    if ext == ".vrm":
        return "asset", "vrm_extension", 0.98
    if mime_l in VRM_MIME_TYPES:
        return "asset", "vrm_mime", 0.98
    if mime_l in GLTF_MIME_TYPES:
        return "asset", "gltf_candidate", 0.65

    if field_l in METADATA_FIELD_NAMES:
        return "metadata", "metadata_field", 0.9
    if ext in {".json", ".jsonld"} or _DATA_JSON_RE.match(url):
        return "metadata", "json_resource", 0.85
    if mime_l in JSON_MIME_TYPES:
        return "metadata", "json_mime", 0.9

    # Generic uri/url fields are deliberately not followed unless the value
    # provides a strong document or asset signal. This prevents arbitrary HTML
    # crawling through project/external links.
    return None, "unclassified", 0.0


def discover_links(
    document: Any,
    base_url: str,
    *,
    max_links: int = 500,
) -> list[DiscoveredLink]:
    """Recursively discover metadata documents and candidate VRM assets.

    Embedded JSON strings are parsed once and walked too. The output is
    deduplicated by (kind, canonical URL), while retaining the first evidence
    path and reason.
    """
    found: dict[tuple[str, str], DiscoveredLink] = {}

    def add(field: str, value: str, path: str, mime: str) -> None:
        if len(found) >= max_links:
            return
        try:
            if _looks_absolute(value):
                url = canonicalize_uri(value)
            elif field.lower() in URL_FIELD_NAMES and _looks_relative_url(value):
                url = resolve_uri(base_url, value)
            else:
                return
        except PermanentCrawlError:
            return
        kind, reason, confidence = _classify(field, url, mime)
        if not kind:
            return
        relation = "document_references_asset" if kind == "asset" else "document_references_metadata"
        found.setdefault(
            (kind, url),
            DiscoveredLink(
                kind=kind,
                url=url,
                path=path,
                relation=relation,
                reason=reason,
                confidence=confidence,
            ),
        )

    def walk(obj: Any, path: str = "$") -> None:
        if len(found) >= max_links:
            return
        if isinstance(obj, dict):
            mime = _mime_from_dict(obj)
            for key, value in obj.items():
                child_path = f"{path}.{key}"
                if isinstance(value, str):
                    stripped = value.strip()
                    if stripped.startswith(("{", "[")) and len(stripped) <= 1_000_000:
                        try:
                            walk(json.loads(stripped), child_path + "::<json>")
                        except json.JSONDecodeError:
                            pass
                    add(key, value, child_path, mime)
                else:
                    walk(value, child_path)
        elif isinstance(obj, list):
            for index, item in enumerate(obj):
                walk(item, f"{path}[{index}]")

    walk(document)
    return list(found.values())


def iter_json_paths(document: Any, *, root: str = "$") -> Iterable[tuple[str, Any]]:
    """Yield every value with a stable JSON-path-like location."""
    yield root, document
    if isinstance(document, dict):
        for key, value in document.items():
            yield from iter_json_paths(value, root=f"{root}.{key}")
    elif isinstance(document, list):
        for index, value in enumerate(document):
            yield from iter_json_paths(value, root=f"{root}[{index}]")
