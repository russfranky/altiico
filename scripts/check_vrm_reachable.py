"""Check whether each collection's VRM file is actually reachable.

Knowing a VRM resolves is the biggest onboarding blocker: IPFS gateways die
(e.g. cloudflare-ipfs.com shut down), CDNs 404, hosts go away. This probes a
concrete VRM URL per collection with a partial-GLB range request (reusing
extract_vrm_meta) and records the result in the reachability columns from
migration 013.

Strategy per collection:
  1. Pick a concrete URL: vrm_url_https if it is syntactically concrete, else
     substitute a sample id into a syntactically valid vrm_url_pattern.
  2. Reject prose/descriptive patterns rather than sending them to the network.
  3. Fetch the concrete URL (range request + GLB validation).
  4. If it is an IPFS URL and the stored gateway fails, retry via ipfs.io and
     dweb.link so we learn whether the FILE exists even if the gateway is dead.

Statuses:
  ok_vrm             fetched + parsed as a GLB/VRM   -> reachable=1
  reachable_not_vrm  fetched bytes but not a valid VRM/GLB -> reachable=1
  http_404 / http_5xx / timeout / dns_or_conn / error -> reachable=0
  no_url             nothing testable                -> reachable stays NULL
"""

from __future__ import annotations

import argparse
import re
import socket
import sqlite3
import sys
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.extract_vrm_meta import fetch_vrm_meta  # noqa: E402

TOKEN_RE = re.compile(r"\{token_id\}|\{id\}|\{token\}|%d", re.IGNORECASE)
UNRESOLVED_TEMPLATE_RE = re.compile(r"\{[^}]+\}|%[a-z]", re.IGNORECASE)
IPFS_PATH_RE = re.compile(r"/ipfs/([A-Za-z0-9]+)(/.*)?$")
GLB_PARSE_HINTS = ("Not a GLB", "no VRM extension", "Unsupported GLB", "First chunk is not JSON", "Header too short")


def _syntactically_concrete_url(value: str) -> bool:
    """Return True only for network-fetchable URL syntax, never prose labels."""
    if not value or any(ch.isspace() for ch in value):
        return False
    if UNRESOLVED_TEMPLATE_RE.search(value):
        return False
    if value.startswith("ipfs://"):
        remainder = value[len("ipfs://"):]
        return bool(remainder and "/" not in remainder[:1] and " " not in remainder)
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def concrete_url(row: dict[str, Any], sample_id: str = "1") -> str | None:
    u = (row.get("vrm_url_https") or "").strip()
    if u and _syntactically_concrete_url(u):
        return u

    p = (row.get("vrm_url_pattern") or "").strip()
    if not p:
        return None
    if not (p.startswith("http://") or p.startswith("https://") or p.startswith("ipfs://")):
        p = "https://" + p  # scheme-less host, e.g. nft.example.com/{id}.vrm
    candidate = TOKEN_RE.sub(str(sample_id), p)
    return candidate if _syntactically_concrete_url(candidate) else None


def _normalize(url: str) -> str:
    if url.startswith("ipfs://"):
        return "https://ipfs.io/ipfs/" + url[len("ipfs://"):]
    return url


def _ipfs_fallbacks(url: str) -> list[str]:
    m = IPFS_PATH_RE.search(url)
    if not m:
        return []
    cid, path = m.group(1), (m.group(2) or "")
    return [f"https://ipfs.io/ipfs/{cid}{path}", f"https://dweb.link/ipfs/{cid}{path}"]


def check_url(url: str, timeout: float = 25.0) -> dict[str, Any]:
    """Return {reachable, status, http, bytes, used_url} for a concrete URL."""
    candidates = [_normalize(url)]
    for fb in _ipfs_fallbacks(url):
        if fb not in candidates:
            candidates.append(fb)

    last_status, last_http = "error", None
    for u in candidates:
        try:
            res = fetch_vrm_meta(u, timeout=timeout)
            return {"reachable": 1, "status": "ok_vrm", "http": 200,
                    "bytes": res.get("total_length"), "used_url": u}
        except urllib.error.HTTPError as e:
            last_status = f"http_{e.code}" if e.code < 500 else "http_5xx"
            last_http = e.code
            continue
        except ValueError as e:
            msg = str(e)
            if any(h in msg for h in GLB_PARSE_HINTS):
                # We fetched bytes; they just are not a valid VRM/GLB.
                return {"reachable": 1, "status": "reachable_not_vrm", "http": 200,
                        "bytes": None, "used_url": u}
            last_status, last_http = "error", None
            continue
        except (socket.timeout, TimeoutError):
            last_status = "timeout"
            continue
        except urllib.error.URLError as e:
            reason = str(getattr(e, "reason", e)).lower()
            last_status = "timeout" if "timed out" in reason else "dns_or_conn"
            continue
        except Exception:  # noqa: BLE001
            last_status = "error"
            continue
    return {"reachable": 0, "status": last_status, "http": last_http,
            "bytes": None, "used_url": candidates[0]}


def _row_factory(cur: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {c[0]: row[idx] for idx, c in enumerate(cur.description)}


def load_targets(conn: sqlite3.Connection, tiers: set[str]) -> list[dict[str, Any]]:
    ph = ",".join("?" for _ in tiers)
    cur = conn.execute(
        f"SELECT id, name, tier, vrm_url_https, vrm_url_pattern FROM collections WHERE tier IN ({ph})",
        tuple(tiers),
    )
    cur.row_factory = _row_factory  # type: ignore[assignment]
    return list(cur.fetchall())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Probe VRM file reachability per collection.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--tier", default="A,B")
    ap.add_argument("--sample-id", default="1", help="id to substitute into {id} patterns")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", default=None, help="ISO timestamp to stamp (default: current UTC)")
    args = ap.parse_args(argv)

    tiers = {t.strip().upper() for t in args.tier.split(",") if t.strip()}
    stamp = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = sqlite3.connect(args.db)
    try:
        rows = load_targets(conn, tiers)
    finally:
        conn.close()

    jobs = []
    for r in rows:
        url = concrete_url(r, args.sample_id)
        jobs.append((r, url))

    def run(job):
        r, url = job
        if not url:
            return r, url, {"reachable": None, "status": "no_url", "http": None, "bytes": None, "used_url": None}
        return r, url, check_url(url, timeout=args.timeout)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r, url, res in ex.map(run, jobs):
            results.append((r, url, res))
            icon = {"ok_vrm": "🟢", "reachable_not_vrm": "🟡", "no_url": "·"}.get(res["status"], "🔴")
            size = f" {res['bytes']//1024}KB" if res.get("bytes") else ""
            print(f"  {icon} {r['name'][:34]:34} {res['status']}{size}  {(res.get('used_url') or '')[:60]}", file=sys.stderr)

    tallies: dict[str, int] = {}
    for _, _, res in results:
        tallies[res["status"]] = tallies.get(res["status"], 0) + 1
    print(f"\nsummary: {tallies}", file=sys.stderr)

    if args.dry_run:
        print("dry-run: no DB writes", file=sys.stderr)
        return 0

    conn = sqlite3.connect(args.db)
    try:
        for r, _, res in results:
            conn.execute(
                """UPDATE collections SET vrm_reachable=?, vrm_check_status=?, vrm_check_http=?,
                   vrm_check_bytes=?, vrm_check_url=?, vrm_checked_at=? WHERE id=?""",
                (res["reachable"], res["status"], res["http"], res["bytes"], res["used_url"], stamp, r["id"]),
            )
        conn.commit()
    finally:
        conn.close()
    print(f"wrote reachability for {len(results)} collections", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
