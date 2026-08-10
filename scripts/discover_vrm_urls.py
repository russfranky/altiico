"""Discover a collection's VRM URL on-chain, then validate it resolves.

Fills the biggest catalog gap: collections with no VRM URL on record. For each
EVM collection with a contract, this calls ``tokenURI(id)`` over a public RPC,
fetches the token metadata, scans it for a VRM pointer (reusing
discover_metadata_fields.scan_metadata), and validates the candidate with the
partial-GLB reachability checker. A confirmed, reachable VRM is written back to
the collection (vrm_url_https + the migration-013 reachability columns).

No API keys — public RPCs + IPFS/Arweave gateways only.
"""

from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discover_metadata_fields import scan_metadata  # noqa: E402
from scripts.check_vrm_reachable import check_url  # noqa: E402

# Public RPCs by catalog chain name (no key). First that answers wins.
RPCS: dict[str, list[str]] = {
    "ethereum": ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"],
    "base": ["https://base-rpc.publicnode.com", "https://mainnet.base.org"],
    "polygon": ["https://polygon-bor-rpc.publicnode.com", "https://polygon-rpc.com"],
    "optimism": ["https://optimism-rpc.publicnode.com", "https://mainnet.optimism.io"],
    "arbitrum": ["https://arbitrum-one-rpc.publicnode.com"],
    "shape": ["https://mainnet.shape.network"],
    "ape_chain": ["https://apechain.calderachain.xyz/http"],
}
TOKENURI_SELECTOR = "0xc87b56dd"  # tokenURI(uint256)


def eth_call(rpc: str, to: str, data: str, timeout: float = 20.0) -> Any:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": to, "data": data}, "latest"]}).encode()
    req = urllib.request.Request(rpc, body, {"Content-Type": "application/json", "User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def token_uri(chain: str, contract: str, token_id: int) -> str | None:
    data = TOKENURI_SELECTOR + f"{token_id:064x}"
    for rpc in RPCS.get(chain, []):
        try:
            res = eth_call(rpc, contract, data)
            hexs = res.get("result")
            if not hexs or hexs == "0x":
                continue
            b = bytes.fromhex(hexs[2:])
            if len(b) < 64:
                continue
            strlen = int.from_bytes(b[32:64], "big")
            s = b[64:64 + strlen].decode("utf-8", "replace").strip("\x00").strip()
            if s:
                return s
        except Exception:  # noqa: BLE001
            continue
    return None


def fetch_metadata(uri: str, timeout: float = 20.0) -> Any:
    """Resolve a tokenURI (ipfs/ar/data/https) to a metadata dict."""
    if uri.startswith("data:application/json"):
        payload = uri.split(",", 1)[1]
        raw = base64.b64decode(payload) if ";base64," in uri else payload.encode()
        return json.loads(raw)
    url = uri
    if uri.startswith("ipfs://"):
        url = "https://ipfs.io/ipfs/" + uri[len("ipfs://"):]
    elif uri.startswith("ar://"):
        url = "https://arweave.net/" + uri[len("ar://"):]
    req = urllib.request.Request(url, headers={"User-Agent": "vrm-catalog/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8", "replace"))


def _row_factory(cur: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {c[0]: row[idx] for idx, c in enumerate(cur.description)}


def discover_one(row: dict[str, Any], token_ids: list[int], timeout: float) -> dict[str, Any]:
    chain, contract = row.get("chain"), row.get("contract")
    if not contract or chain not in RPCS:
        return {"status": "skip", "reason": f"chain '{chain}' unsupported / no contract"}
    uri = None
    for tid in token_ids:
        uri = token_uri(chain, contract, tid)
        if uri:
            break
    if not uri:
        return {"status": "no_tokenuri"}
    try:
        meta = fetch_metadata(uri, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return {"status": "metadata_error", "reason": str(e)[:60], "tokenuri": uri}
    cands = scan_metadata(meta) if isinstance(meta, (dict, list)) else []
    if not cands:
        return {"status": "no_vrm_pointer", "tokenuri": uri}
    # Validate each candidate until one is a reachable VRM.
    for c in cands:
        val = c.get("url")
        if not val:
            continue
        res = check_url(val, timeout=timeout)
        if res["reachable"] == 1:
            return {"status": res["status"], "vrm_url": val, "check": res, "tokenuri": uri}
    # None reachable — report the first candidate + its failure.
    first = cands[0].get("url")
    return {"status": "vrm_pointer_unreachable", "vrm_url": first,
            "check": check_url(first, timeout=timeout) if first else None, "tokenuri": uri}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Discover + validate collection VRM URLs on-chain.")
    ap.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    ap.add_argument("--where", default="vrm_check_status='no_url' OR vrm_url_https IS NULL OR vrm_url_https=''",
                    help="SQL predicate selecting collections to scan")
    ap.add_argument("--tiers", default="A,B,C")
    ap.add_argument("--token-ids", default="1,0,2", help="token ids to try, in order")
    ap.add_argument("--limit", type=int, default=0, help="max collections (0 = all)")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--now", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    tiers = tuple(t.strip().upper() for t in args.tiers.split(",") if t.strip())
    token_ids = [int(x) for x in args.token_ids.split(",")]
    stamp = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = sqlite3.connect(args.db)
    conn.row_factory = _row_factory  # type: ignore[assignment]
    ph = ",".join("?" for _ in tiers)
    sql = f"SELECT id,name,chain,contract,vrm_url_https,vrm_check_status FROM collections WHERE tier IN ({ph}) AND ({args.where}) ORDER BY tier,name"
    rows = list(conn.execute(sql, tiers))
    if args.limit:
        rows = rows[:args.limit]
    conn.close()

    print(f"scanning {len(rows)} collections on-chain for VRM URLs…\n", file=sys.stderr)
    found = []
    tallies: dict[str, int] = {}
    for row in rows:
        r = discover_one(row, token_ids, args.timeout)
        st = r["status"]
        tallies[st] = tallies.get(st, 0) + 1
        icon = "🟢" if st == "ok_vrm" else ("🟡" if st == "reachable_not_vrm" else ("🔎" if st == "vrm_pointer_unreachable" else "·"))
        extra = ""
        if r.get("vrm_url"):
            extra = "  " + (r["vrm_url"][:56])
        print(f"  {icon} {row['name'][:30]:30} {st}{extra}", file=sys.stderr)
        # Record any discovered pointer (reachable or not) — a known-but-dead VRM
        # URL is more actionable than "no_url". Never downgrade a collection that
        # already has a confirmed-live VRM.
        if r.get("vrm_url") and r.get("check") and row.get("vrm_check_status") != "ok_vrm":
            found.append((row, r))

    print(f"\nsummary: {tallies}", file=sys.stderr)
    print(f"newly discovered reachable VRM URLs: {len(found)}", file=sys.stderr)

    if args.dry_run or not found:
        if args.dry_run:
            print("dry-run: no DB writes", file=sys.stderr)
        return 0

    conn = sqlite3.connect(args.db)
    try:
        for row, r in found:
            chk = r["check"]
            conn.execute(
                """UPDATE collections SET vrm_url_https=?, vrm_reachable=?, vrm_check_status=?,
                   vrm_check_http=?, vrm_check_bytes=?, vrm_check_url=?, vrm_checked_at=? WHERE id=?""",
                (r["vrm_url"], chk["reachable"], chk["status"], chk["http"], chk["bytes"],
                 chk["used_url"], stamp, row["id"]),
            )
        conn.commit()
    finally:
        conn.close()
    print(f"wrote {len(found)} discovered VRM URLs to the DB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
