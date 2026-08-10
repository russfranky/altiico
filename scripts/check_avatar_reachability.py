"""Check whether each individual avatar's VRM file is reachable.

Collection-level checks validated one sample VRM per collection. This checks
every avatar. It reads only the first 12 bytes of each file and verifies the GLB
magic ('glTF'), which is enough to prove the bytes are really there and really a
model — no full download, no metadata parse.
"""

from __future__ import annotations

import argparse
import socket
import sqlite3
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
GLB_MAGIC = b"glTF"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def probe(url: str, timeout: float) -> dict[str, Any]:
    """Range-request the first 12 bytes and check the GLB magic."""
    req = urllib.request.Request(url, headers={
        "Range": "bytes=0-11", "Accept-Encoding": "identity",
        "User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            data = r.read(12)
            code = getattr(r, "status", None) or r.getcode()
        if data[:4] == GLB_MAGIC:
            return {"reachable": 1, "status": "ok_glb", "http": code}
        return {"reachable": 1, "status": "not_glb", "http": code}
    except urllib.error.HTTPError as e:
        s = f"http_{e.code}" if e.code < 500 else "http_5xx"
        return {"reachable": 0, "status": s, "http": e.code}
    except (socket.timeout, TimeoutError):
        return {"reachable": 0, "status": "timeout", "http": None}
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e)).lower()
        return {"reachable": 0, "status": "timeout" if "timed out" in reason else "dns_or_conn", "http": None}
    except Exception:  # noqa: BLE001
        return {"reachable": 0, "status": "error", "http": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check reachability of every avatar VRM.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--collection", default=None, help="limit to one collection_id")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--recheck", action="store_true", help="re-check already-checked avatars")
    ap.add_argument("--now", default=None)
    args = ap.parse_args(argv)

    stamp = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    where = ["model_file_url IS NOT NULL", "model_file_url != ''"]
    params: list[Any] = []
    if args.collection:
        where.append("collection_id = ?"); params.append(args.collection)
    if not args.recheck:
        where.append("check_status IS NULL")
    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        f"SELECT id, collection_id, model_file_url FROM avatars WHERE {' AND '.join(where)} "
        f"ORDER BY collection_id, id" + (f" LIMIT {args.limit}" if args.limit else ""), params).fetchall()
    conn.close()

    print(f"checking {len(rows)} avatar VRM URLs ({args.workers} workers)…", file=sys.stderr)
    results, tallies, done = [], {}, 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for (aid, cid, url), res in zip(rows, ex.map(lambda r: probe(r[2], args.timeout), rows)):
            results.append((res["reachable"], res["status"], res["http"], stamp, aid))
            tallies[res["status"]] = tallies.get(res["status"], 0) + 1
            done += 1
            if done % 250 == 0:
                print(f"  {done}/{len(rows)} … {tallies}", file=sys.stderr)

    conn = sqlite3.connect(args.db)
    conn.executemany("UPDATE avatars SET reachable=?, check_status=?, check_http=?, checked_at=? WHERE id=?", results)
    conn.commit()
    ok = conn.execute("SELECT COUNT(*) FROM avatars WHERE reachable=1").fetchone()[0]
    tot = conn.execute("SELECT COUNT(*) FROM avatars").fetchone()[0]
    conn.close()
    print(f"\nsummary: {tallies}", file=sys.stderr)
    print(f"reachable overall: {ok}/{tot}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
