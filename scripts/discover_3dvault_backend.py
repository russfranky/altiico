#!/usr/bin/env python3
"""Probe 3dvault page assets for machine-readable partner collection identity.

The homepage renders partner collections largely as anonymous cached images. This
probe follows same-origin scripts/styles and extracts API/JSON endpoints, project
names, contract addresses, marketplace slugs, and model-file signals so the
3dvault source can yield actual resolvable projects instead of anonymous logos.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = "https://3dvault.xyz/en/"
UA = "vrm-catalog/1.0 (+https://github.com/russfranky/vrm-catalog)"
URL_RE = re.compile(r"https?://[^\s\"'<>\\)]+")
CONTRACT_RE = re.compile(r"0x[a-fA-F0-9]{40}")
MODEL_RE = re.compile(r"https?://[^\s\"'<>\\)]+\.(?:vrm|glb|gltf)(?:\?[^\s\"'<>\\)]*)?", re.I)
OPENSEA_RE = re.compile(r"https?://(?:www\.)?opensea\.io/collection/([a-zA-Z0-9_-]+)", re.I)
KEYWORD_RE = re.compile(r"(?i)(avatar|collection|partner|metaverse|wearable|project|nft|vrm|3d)")


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: list[str] = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        for key in ("src", "href"):
            value = d.get(key)
            if value and tag in {"script", "link"}:
                self.assets.append(value)


def fetch(session: requests.Session, url: str, timeout: float) -> tuple[int, str, str]:
    r = session.get(url, timeout=timeout, headers={"User-Agent": UA})
    ctype = r.headers.get("content-type", "")
    text = r.text if ("text" in ctype or "json" in ctype or url.endswith((".js", ".css", ".json", "/"))) else ""
    return r.status_code, ctype, text


def decoded_views(text: str) -> list[str]:
    """Return original + conservative decoded variants for JSON/JS escaped strings."""
    views = [text]
    simple = text.replace(r"\/", "/").replace(r'\"', '"').replace(r"\'", "'")
    if simple not in views:
        views.append(simple)
    entity = html_lib.unescape(simple)
    if entity not in views:
        views.append(entity)
    # Locale endpoint is JSON-ish JavaScript. Decode common unicode escapes without
    # trying to execute arbitrary JS.
    try:
        unicode_decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), entity)
        if unicode_decoded not in views:
            views.append(unicode_decoded)
    except Exception:
        pass
    return views


def extract_urls(text: str) -> list[str]:
    urls: set[str] = set()
    for view in decoded_views(text):
        for url in URL_RE.findall(view):
            urls.add(url.rstrip(".,;"))
    return sorted(urls)


def interesting_urls(text: str) -> list[str]:
    urls = []
    for url in extract_urls(text):
        low = url.lower()
        if any(k in low for k in ("api", "graphql", "json", "avatar", "collection", "partner", "nft", "vrm", "opensea")):
            urls.append(url)
    return sorted(set(urls))


def contracts_in(text: str) -> list[str]:
    out: set[str] = set()
    for view in decoded_views(text):
        out.update(CONTRACT_RE.findall(view))
    return sorted(out)


def models_in(text: str) -> list[str]:
    out: set[str] = set()
    for view in decoded_views(text):
        out.update(MODEL_RE.findall(view))
    return sorted(out)


def slugs_in(text: str) -> list[str]:
    out: set[str] = set()
    for view in decoded_views(text):
        out.update(OPENSEA_RE.findall(view))
    return sorted(out)


def string_hints(text: str) -> list[str]:
    hints = []
    for view in decoded_views(text):
        for raw in re.findall(r"[\"']([^\"']{3,160})[\"']", view):
            s = raw.strip()
            if KEYWORD_RE.search(s) and not s.startswith(("http://", "https://")):
                hints.append(s)
    return sorted(set(hints))[:1000]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=ROOT)
    ap.add_argument("--output", type=Path, default=Path("data/3dvault_backend_probe.json"))
    ap.add_argument("--timeout", type=float, default=15)
    ap.add_argument("--max-assets", type=int, default=80)
    args = ap.parse_args()

    session = requests.Session()
    status, ctype, html = fetch(session, args.url, args.timeout)
    parser = AssetParser(); parser.feed(html)
    origin = urlparse(args.url).netloc
    assets = []
    for raw in parser.assets:
        u = urljoin(args.url, raw)
        if urlparse(u).netloc == origin and u not in assets:
            assets.append(u)
    assets = assets[: args.max_assets]

    records = []
    all_urls: set[str] = set()
    all_contracts: set[str] = set(contracts_in(html))
    all_models: set[str] = set(models_in(html))
    all_slugs: set[str] = set(slugs_in(html))
    all_hints: set[str] = set(string_hints(html))

    for url in assets:
        try:
            st, ct, text = fetch(session, url, args.timeout)
            urls = interesting_urls(text)
            contracts = contracts_in(text)
            models = models_in(text)
            slugs = slugs_in(text)
            hints = string_hints(text)
            all_urls.update(urls); all_contracts.update(contracts); all_models.update(models); all_slugs.update(slugs); all_hints.update(hints)
            records.append({"url": url, "status": st, "contentType": ct, "bytesText": len(text), "interestingUrls": urls[:200], "contracts": contracts, "modelUrls": models, "openseaSlugs": slugs, "stringHints": hints[:200]})
        except Exception as exc:
            records.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})

    endpoints = []
    for url in sorted(all_urls)[:120]:
        try:
            st, ct, text = fetch(session, url, args.timeout)
            contracts = contracts_in(text)
            models = models_in(text)
            slugs = slugs_in(text)
            hints = string_hints(text)
            all_contracts.update(contracts); all_models.update(models); all_slugs.update(slugs); all_hints.update(hints)
            endpoints.append({"url": url, "status": st, "contentType": ct, "preview": text[:3000], "contracts": contracts, "modelUrls": models, "openseaSlugs": slugs, "stringHints": hints[:200]})
        except Exception as exc:
            endpoints.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})

    out = {
        "schema": "3dvault-backend-probe-v2",
        "source": args.url,
        "pageStatus": status,
        "pageContentType": ctype,
        "summary": {
            "assetsInspected": len(records),
            "candidateEndpoints": len(all_urls),
            "endpointsFetched": len(endpoints),
            "contractSignals": len(all_contracts),
            "modelUrlSignals": len(all_models),
            "openseaSlugSignals": len(all_slugs),
            "stringHints": len(all_hints),
        },
        "contracts": sorted(all_contracts),
        "modelUrls": sorted(all_models),
        "openseaSlugs": sorted(all_slugs),
        "interestingUrls": sorted(all_urls),
        "stringHints": sorted(all_hints),
        "assets": records,
        "endpoints": endpoints,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(json.dumps({"openseaSlugs": out["openseaSlugs"], "modelUrls": out["modelUrls"][:20], "contracts": out["contracts"][:20]}, indent=2))


if __name__ == "__main__":
    main()
