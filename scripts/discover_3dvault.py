#!/usr/bin/env python3
"""Discover 3D avatar/project leads from 3dvault.xyz.

3dvault is a lead/relationship source, never canonical VRM proof. This crawler
extracts its curated Partner Avatar Collections and compatible metaverse graph,
then follows directly linked project pages one hop to capture identity/model
signals that can feed the normal validation pipeline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

BASE = Path(__file__).parent.parent
DEFAULT_URL = "https://3dvault.xyz/en/"
DEFAULT_OUTPUT = BASE / "data" / "3dvault_discovery.json"
MODEL_RE = re.compile(r"(?:ipfs://|https?://|ar://)[^\s\"'<>]+?\.(?:vrm|glb|gltf)(?:\?[^\s\"'<>]*)?", re.I)
CONTRACT_RE = re.compile(r"0x[a-fA-F0-9]{40}")
OPENSEA_RE = re.compile(r"https?://(?:www\.)?opensea\.io/(?:collection/[^\s\"'<>/?#]+|assets/[^\s\"'<>]+)", re.I)
HASHLIKE_LABEL_RE = re.compile(
    r"^[a-f0-9]{16,}(?:[_-][a-f0-9]{8,})+(?:\.(?:png|jpe?g|gif|webp|svg))+$",
    re.I,
)
GENERIC_LABEL_RE = re.compile(r"(?:image|logo|learn more|website|visit)", re.I)


class LinkImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_anchor: dict[str, Any] | None = None
        self.anchors: list[dict[str, Any]] = []
        self.images: list[dict[str, str]] = []
        self.text_parts: list[str] = []
        self.title = ""
        self._in_title = False
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "a":
            self.current_anchor = {
                "href": a.get("href", ""),
                "text": [],
                "images": [],
                "aria": a.get("aria-label") or "",
                "name": a.get("data-name") or a.get("data-title") or a.get("title") or "",
            }
        elif tag == "img":
            img = {
                "src": a.get("src") or a.get("data-src") or a.get("data-lazy-src") or "",
                "alt": a.get("alt", ""),
                "title": a.get("title", ""),
                "aria": a.get("aria-label") or a.get("aria-labelledby") or "",
                "name": a.get("data-name") or a.get("data-title") or a.get("data-label") or "",
            }
            self.images.append(img)
            if self.current_anchor is not None:
                self.current_anchor["images"].append(img)
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current_anchor is not None:
            self.current_anchor["text"] = " ".join(self.current_anchor["text"]).strip()
            self.anchors.append(self.current_anchor)
            self.current_anchor = None
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        self.text_parts.append(text)
        if self.current_anchor is not None:
            self.current_anchor["text"].append(text)
        if self._in_title:
            self.title += (" " if self.title else "") + text


class SectionParser(LinkImageParser):
    """Classify homepage anchors/images by the nearest relevant text section."""
    def __init__(self) -> None:
        super().__init__()
        self.section = "other"
        self.section_anchors: dict[str, list[dict[str, Any]]] = {"avatar_collections": [], "metaverse_platforms": []}
        self.section_images: dict[str, list[dict[str, str]]] = {"avatar_collections": [], "metaverse_platforms": []}

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        low = text.lower()
        if "partner avatar collections" in low:
            self.section = "avatar_collections"
        elif "compatible / partner metaverse platforms" in low or "compatible / partner" in low and "metaverse" in low:
            self.section = "metaverse_platforms"
        super().handle_data(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        before_anchor = self.current_anchor
        super().handle_starttag(tag, attrs)
        if tag == "img" and self.section in self.section_images:
            self.section_images[self.section].append(self.images[-1])
        if tag == "a" and self.section in self.section_anchors and before_anchor is None:
            # anchor is appended on close; remember section on the object
            assert self.current_anchor is not None
            self.current_anchor["section"] = self.section

    def handle_endtag(self, tag: str) -> None:
        current = self.current_anchor
        super().handle_endtag(tag)
        if tag == "a" and current is not None:
            section = current.get("section")
            if section in self.section_anchors:
                self.section_anchors[section].append(current)


def fetch(session: requests.Session, url: str, timeout: int) -> tuple[str, int, str]:
    resp = session.get(url, timeout=timeout, allow_redirects=True, headers={"Accept": "text/html,application/xhtml+xml"})
    resp.raise_for_status()
    return resp.text, resp.status_code, resp.url


def normalize_url(base: str, value: str) -> str:
    if not value or value.startswith(("javascript:", "mailto:", "tel:", "#")):
        return ""
    return urljoin(base, value)


def is_hashlike_label(value: str) -> bool:
    """True when a label is just a content-hashed asset filename, not a collection name."""
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return False
    basename = text.rsplit("/", 1)[-1]
    return bool(HASHLIKE_LABEL_RE.fullmatch(basename))


def human_label(*pieces: Any) -> str:
    for piece in pieces:
        text = " ".join(str(piece or "").split()).strip()
        if not text:
            continue
        if GENERIC_LABEL_RE.fullmatch(text):
            continue
        if is_hashlike_label(text):
            continue
        return text
    return ""


def label_for(anchor: dict[str, Any]) -> str:
    pieces = [anchor.get("text", ""), anchor.get("aria", ""), anchor.get("name", "")]
    for img in anchor.get("images") or []:
        pieces.extend([
            img.get("name", ""),
            img.get("aria", ""),
            img.get("alt", ""),
            img.get("title", ""),
        ])
    label = human_label(*pieces)
    if label:
        return label
    href = anchor.get("href", "")
    if href:
        host = urlparse(href).netloc.replace("www.", "")
        if host and not is_hashlike_label(host):
            return host
    return ""


def page_signals(session: requests.Session, url: str, timeout: int) -> dict[str, Any]:
    try:
        html, status, final_url = fetch(session, url, timeout)
    except Exception as exc:  # discovery must keep going
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}
    parser = LinkImageParser()
    parser.feed(html)
    links = sorted({normalize_url(final_url, a.get("href", "")) for a in parser.anchors} - {""})
    text = " ".join(parser.text_parts)
    models = sorted(set(MODEL_RE.findall(html)))
    contracts = sorted(set(CONTRACT_RE.findall(html)))
    opensea = sorted(set(OPENSEA_RE.findall(html)))
    return {
        "url": final_url,
        "status": status,
        "title": parser.title,
        "description": parser.meta.get("description") or parser.meta.get("og:description") or "",
        "links": links[:250],
        "modelUrls": models[:100],
        "contracts": contracts[:100],
        "openseaUrls": opensea[:100],
        "mentions": {
            "vrm": len(re.findall(r"\bVRM\b", text, re.I)),
            "glb": len(re.findall(r"\bGLB\b", text, re.I)),
            "gltf": len(re.findall(r"\bglTF\b", text, re.I)),
            "avatar": len(re.findall(r"\bavatars?\b", text, re.I)),
        },
    }


def lead_id(kind: str, label: str, url: str, image: str) -> str:
    return hashlib.sha256(f"{kind}|{label}|{url}|{image}".encode()).hexdigest()[:20]


def build_leads(base_url: str, anchors: list[dict[str, Any]], images: list[dict[str, str]], kind: str) -> list[dict[str, Any]]:
    leads: list[dict[str, Any]] = []
    used_images: set[str] = set()
    for a in anchors:
        url = normalize_url(base_url, a.get("href", ""))
        imgs = a.get("images") or []
        image = normalize_url(base_url, imgs[0].get("src", "")) if imgs else ""
        if image:
            used_images.add(image)
        label = label_for({**a, "href": url})
        if not (url or image or label):
            continue
        leads.append({
            "leadId": lead_id(kind, label, url, image),
            "kind": kind,
            "label": label,
            "url": url,
            "imageUrl": image,
            "source": "3dvault",
            "sourceRole": "curated_relationship_lead",
            "labelQuality": "human" if label else "unresolved",
        })
    # Preserve image-only partner entries when the site does not wrap logos in links.
    for img in images:
        image = normalize_url(base_url, img.get("src", ""))
        if not image or image in used_images:
            continue
        label = " ".join((
            img.get("name") or img.get("aria") or img.get("alt") or img.get("title") or ""
        ).split())
        if is_hashlike_label(label):
            label = ""
        leads.append({
            "leadId": lead_id(kind, label, "", image),
            "kind": kind,
            "label": label,
            "url": "",
            "imageUrl": image,
            "source": "3dvault",
            "sourceRole": "curated_image_lead",
            "labelQuality": "human" if label else "unresolved",
        })
    # exact dedupe
    out: dict[str, dict[str, Any]] = {}
    for lead in leads:
        out[lead["leadId"]] = lead
    return list(out.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--max-follow", type=int, default=50)
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "vrm-catalog-research/1.0 (+https://github.com/russfranky/vrm-catalog)"})
    html, status, final_url = fetch(session, args.url, args.timeout)
    parser = SectionParser()
    parser.feed(html)

    avatar_leads = build_leads(final_url, parser.section_anchors["avatar_collections"], parser.section_images["avatar_collections"], "avatar_collection")
    platform_leads = build_leads(final_url, parser.section_anchors["metaverse_platforms"], parser.section_images["metaverse_platforms"], "metaverse_platform")

    followed = 0
    for lead in avatar_leads:
        url = lead.get("url") or ""
        if not url or followed >= args.max_follow:
            continue
        host = urlparse(url).netloc.lower()
        # Skip pure asset/CDN/social links; keep project/collection sites.
        if not host or host.endswith(("3dvault.xyz", "twitter.com", "x.com", "discord.gg", "instagram.com")):
            continue
        lead["linkedPage"] = page_signals(session, url, args.timeout)
        followed += 1

    model_urls = sorted({m for lead in avatar_leads for m in (lead.get("linkedPage") or {}).get("modelUrls", [])})
    contracts = sorted({c for lead in avatar_leads for c in (lead.get("linkedPage") or {}).get("contracts", [])})
    opensea_urls = sorted({u for lead in avatar_leads for u in (lead.get("linkedPage") or {}).get("openseaUrls", [])})

    report = {
        "schema": "3dvault-discovery-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {"url": final_url, "status": status, "role": "high-value curated 3D-avatar relationship source; lead-only, never VRM proof"},
        "policy": {"promotion": "all model/VRM claims require independent identity resolution and binary GLB 2.0 + VRM/VRMC_vrm validation"},
        "summary": {
            "avatarCollectionLeads": len(avatar_leads),
            "metaversePlatformLeads": len(platform_leads),
            "linkedProjectPagesInspected": followed,
            "modelUrlSignals": len(model_urls),
            "contractSignals": len(contracts),
            "openseaSignals": len(opensea_urls),
        },
        "avatarCollections": avatar_leads,
        "metaversePlatforms": platform_leads,
        "modelUrlSignals": model_urls,
        "contractSignals": contracts,
        "openseaSignals": opensea_urls,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
