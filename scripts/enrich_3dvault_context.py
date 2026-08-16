#!/usr/bin/env python3
"""Enrich image-only 3dvault leads from nearby raw HTML context.

The current 3dvault homepage renders partner logos as hashed image assets and
may omit accessible labels/anchors. This pass inspects the source window around
each image occurrence for sibling href/data attributes, readable text and
project URLs, then follows any recovered external project URL one hop.
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from discover_3dvault import is_hashlike_label, page_signals

BASE = Path(__file__).parent.parent
DEFAULT_REPORT = BASE / "data" / "3dvault_discovery.json"
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
HREF_RE = re.compile(r"(?:href|data-href|data-url|onclick)\s*=\s*[\"']([^\"']+)[\"']", re.I)
TAG_RE = re.compile(r"<[^>]+>")
HASHLIKE_RE = re.compile(
    r"^[a-f0-9]{16,}(?:[_-][a-f0-9]{8,})+(?:\.(?:png|jpe?g|gif|webp|svg))+$",
    re.I,
)
ASSET_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".woff", ".woff2")


def clean_text(fragment: str) -> str:
    text = TAG_RE.sub(" ", fragment)
    text = htmlmod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    # Drop long encoded/script-like runs while retaining human labels.
    chunks = []
    for chunk in re.split(r"[|•·]", text):
        chunk = chunk.strip()
        if not chunk or len(chunk) > 180 or is_hashlike_label(chunk) or HASHLIKE_RE.fullmatch(chunk):
            continue
        if chunk.lower().startswith(("http://", "https://")):
            continue
        chunks.append(chunk)
    return " | ".join(chunks[:6])


def candidate_links(base_url: str, fragment: str) -> list[str]:
    vals = list(HREF_RE.findall(fragment)) + list(URL_RE.findall(fragment))
    out = []
    seen = set()
    for raw in vals:
        # onclick strings can wrap a URL; recover the first one.
        m = URL_RE.search(raw)
        if m:
            raw = m.group(0)
        url = urljoin(base_url, htmlmod.unescape(raw))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        low = parsed.path.lower()
        if low.endswith(ASSET_EXT):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def best_project_url(urls: list[str]) -> str:
    blocked = {
        "3dvault.xyz", "www.3dvault.xyz", "drive.baako.com",
        "twitter.com", "www.twitter.com", "x.com", "www.x.com",
        "instagram.com", "www.instagram.com", "discord.gg", "discord.com",
        "facebook.com", "www.facebook.com", "linkedin.com", "www.linkedin.com",
    }
    for url in urls:
        if urlparse(url).netloc.lower() not in blocked:
            return url
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--window", type=int, default=2200)
    args = ap.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    source_url = report.get("source", {}).get("url") or "https://3dvault.xyz/en/"
    session = requests.Session()
    session.headers.update({"User-Agent": "vrm-catalog-research/1.0 (+https://github.com/russfranky/vrm-catalog)"})
    resp = session.get(source_url, timeout=args.timeout)
    resp.raise_for_status()
    raw = resp.text

    recovered_links = 0
    recovered_labels = 0
    followed = 0
    all_leads = list(report.get("avatarCollections") or []) + list(report.get("metaversePlatforms") or [])
    for lead in all_leads:
        image = lead.get("imageUrl") or ""
        basename = image.rsplit("/", 1)[-1]
        if not basename:
            continue
        pos = raw.find(basename)
        if pos < 0:
            continue
        start = max(0, pos - args.window)
        end = min(len(raw), pos + len(basename) + args.window)
        fragment = raw[start:end]
        links = candidate_links(resp.url, fragment)
        human = clean_text(fragment)
        lead["sourceContext"] = {
            "candidateLinks": links[:30],
            "humanText": human,
        }
        project = best_project_url(links)
        if project and not lead.get("url"):
            lead["url"] = project
            lead["sourceRole"] = "curated_context_link_lead"
            recovered_links += 1
        current_label = str(lead.get("label") or "")
        if human and (not current_label or is_hashlike_label(current_label)):
            # Conservative label: context is a hint, not canonical identity.
            lead["contextLabelHint"] = human[:180]
            if not current_label or is_hashlike_label(current_label):
                recovered_labels += 1
        if lead.get("kind") == "avatar_collection" and lead.get("url"):
            lead["linkedPage"] = page_signals(session, lead["url"], args.timeout)
            followed += 1

    report["summary"]["contextLinksRecovered"] = recovered_links
    report["summary"]["contextLabelsRecovered"] = recovered_labels
    report["summary"]["linkedProjectPagesInspected"] = followed
    report["modelUrlSignals"] = sorted({m for lead in report.get("avatarCollections") or [] for m in (lead.get("linkedPage") or {}).get("modelUrls", [])})
    report["contractSignals"] = sorted({c for lead in report.get("avatarCollections") or [] for c in (lead.get("linkedPage") or {}).get("contracts", [])})
    report["openseaSignals"] = sorted({u for lead in report.get("avatarCollections") or [] for u in (lead.get("linkedPage") or {}).get("openseaUrls", [])})
    report["summary"]["modelUrlSignals"] = len(report["modelUrlSignals"])
    report["summary"]["contractSignals"] = len(report["contractSignals"])
    report["summary"]["openseaSignals"] = len(report["openseaSignals"])
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
