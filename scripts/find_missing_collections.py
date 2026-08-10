"""Find VRM/avatar collections we may have missed.

Aggregates candidate collections from no-key registries and diffs them against
the catalog (by contract, then by normalized name). Anything in a source but
NOT in the catalog is surfaced as a lead for human triage + bookmarking.

Sources (all no-key):
  - Open Source Avatars registry  (projects.json on GitHub)
  - awesome-3D-avatar-collections (README on GitHub)
  - the pre-alpha team's own lists (altiiData.ts / index data.ts) via the local
    clone — the highest-signal "did WE miss it" source

Usage:
  python scripts/find_missing_collections.py [--prealpha /Users/russ/pre-alpha]
  python scripts/find_missing_collections.py --write-leads   # append to discovery_leads.yaml
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent

OSA_PROJECTS = "https://raw.githubusercontent.com/toxsam/open-source-avatars/main/data/projects.json"
AWESOME_README = "https://raw.githubusercontent.com/itsmetamike/awesome-3D-avatar-collections/main/README.md"
CONTRACT_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _get(url: str, timeout: float = 25.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "vrm-catalog/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.read().decode("utf-8", "replace")


# ─── sources ─────────────────────────────────────────────────────────────────


def source_osa() -> list[dict[str, Any]]:
    try:
        data = json.loads(_get(OSA_PROJECTS))
    except Exception as e:  # noqa: BLE001
        print(f"[osa] failed: {e}", file=sys.stderr)
        return []
    projs = data if isinstance(data, list) else data.get("projects", [])
    out = []
    for p in projs:
        out.append({"name": p.get("name") or p.get("title") or "", "contract": None,
                    "chain": p.get("source_type") or p.get("source"), "source": "opensource-avatars"})
    return out


def source_awesome() -> list[dict[str, Any]]:
    try:
        md = _get(AWESOME_README)
    except Exception as e:  # noqa: BLE001
        print(f"[awesome] failed: {e}", file=sys.stderr)
        return []
    out = []
    # Markdown table/list rows: a link title + maybe a contract somewhere on the line.
    for line in md.splitlines():
        if "0x" not in line and "|" not in line:
            continue
        m_name = re.search(r"\[([^\]]{2,60})\]\(", line)
        contracts = CONTRACT_RE.findall(line)
        if m_name and (contracts or "vrm" in line.lower()):
            out.append({"name": m_name.group(1).strip(), "contract": (contracts[0].lower() if contracts else None),
                        "chain": None, "source": "awesome-3d-avatars"})
    return out


def source_prealpha(prealpha_dir: str) -> list[dict[str, Any]]:
    """Parse the team's curated avatar lists from the pre-alpha clone."""
    files = [
        "packages/avatars/lab/src/data/altiiData.ts",
        "packages/avatars/index/src/data.ts",
    ]
    out: list[dict[str, Any]] = []
    for f in files:
        try:
            txt = subprocess.run(["git", "-C", prealpha_dir, "show", f"origin/main:{f}"],
                                 capture_output=True, text=True, timeout=20).stdout
        except Exception as e:  # noqa: BLE001
            print(f"[prealpha] {f} failed: {e}", file=sys.stderr)
            continue
        # Split into object-ish chunks and pull name + nearest contract/chain.
        for chunk in re.split(r"\}\s*,", txt):
            m_name = re.search(r"name:\s*['\"]([^'\"]+)['\"]", chunk)
            if not m_name:
                continue
            m_contract = CONTRACT_RE.search(chunk)
            m_chain = re.search(r"(?:chain|source):\s*['\"]([^'\"]+)['\"]", chunk)
            out.append({"name": m_name.group(1).strip(),
                        "contract": (m_contract.group(0).lower() if m_contract else None),
                        "chain": (m_chain.group(1) if m_chain else None),
                        "source": f"prealpha:{Path(f).name}"})
    return out


# ─── catalog + diff ──────────────────────────────────────────────────────────


def load_catalog(db: str) -> tuple[set[str], set[str]]:
    conn = sqlite3.connect(db)
    contracts, names = set(), set()
    for (c,) in conn.execute("SELECT contract FROM collections WHERE contract IS NOT NULL AND contract!=''"):
        contracts.add(c.lower())
    for (a,) in conn.execute("SELECT address FROM contracts WHERE address IS NOT NULL"):
        contracts.add(a.lower())
    for (n,) in conn.execute("SELECT name FROM collections"):
        names.add(_norm_name(n))
    conn.close()
    return contracts, names


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Find avatar collections missing from the catalog.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--prealpha", default="/Users/russ/pre-alpha")
    ap.add_argument("--write-leads", action="store_true")
    args = ap.parse_args(argv)

    contracts, names = load_catalog(args.db)
    print(f"catalog: {len(contracts)} contracts, {len(names)} names\n", file=sys.stderr)

    candidates = source_osa() + source_awesome()
    if Path(args.prealpha).exists():
        candidates += source_prealpha(args.prealpha)

    # Dedup candidates by (contract or normalized name).
    seen, missing = set(), []
    for c in candidates:
        key = (c["contract"] or "") or _norm_name(c["name"])
        if not key or key in seen:
            continue
        seen.add(key)
        in_catalog = (c["contract"] and c["contract"] in contracts) or (_norm_name(c["name"]) in names)
        if not in_catalog:
            missing.append(c)

    by_source: dict[str, list[dict]] = {}
    for m in missing:
        by_source.setdefault(m["source"], []).append(m)

    print(f"=== MISSING collections ({len(missing)} candidates not in the catalog) ===")
    for src, items in sorted(by_source.items()):
        print(f"\n[{src}] {len(items)}")
        for m in items:
            print(f"  - {m['name']:<38} {m.get('contract') or ''} {m.get('chain') or ''}")

    if args.write_leads and missing:
        leads_path = _REPO_ROOT / "data" / "discovery_leads.yaml"
        import datetime
        block = ["\n# ─── Auto-discovered missing collections (find_missing_collections.py) ───"]
        block.append("gap_finder_candidates:")
        for m in missing:
            block.append(f"  - name: {json.dumps(m['name'])}")
            block.append(f"    contract: {json.dumps(m.get('contract'))}")
            block.append(f"    chain: {json.dumps(m.get('chain'))}")
            block.append(f"    source: {json.dumps(m['source'])}")
            block.append("    review_state: pending")
        with leads_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(block) + "\n")
        print(f"\nappended {len(missing)} candidates to {leads_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
