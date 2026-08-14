#!/usr/bin/env python3
"""Compile base + per-collection research shards into one deterministic JSON file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.catalog_research_store import load_catalog_research

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = ROOT / "data" / "catalog_research.json"
DEFAULT_SHARDS = ROOT / "data" / "catalog_research.d"
DEFAULT_OUTPUT = ROOT / "data" / "catalog_research_merged.json"


def run(base: Path, shards: Path, output: Path) -> dict:
    payload = load_catalog_research(base, shards)
    payload["collections"] = {
        key: payload["collections"][key] for key in sorted(payload["collections"])
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--shards", type=Path, default=DEFAULT_SHARDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run(args.base, args.shards, args.output)
    print(json.dumps({"collections": len(payload["collections"]), "sources": len(payload["sources"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
