# STATE — VRM mapping loop

**Intent:** Map every existing VRM and where it lives, drive collections toward
hubzz-ingress readiness, and surface the sets that meet all criteria — so full
sets are ready to onboard into hubzz.

**Level:** L1 report-only (week one). The loop maps, validates, scores, and
commits the refreshed map. It NEVER onboards a set into hubzz — ingress is a
human gate. Promote to L2 only after the map proves stable.

## Readiness criteria (hubzz ingress)
A set is READY when all three CRITICAL criteria pass:
- `vrm_ok` — a reachable, valid VRM (`vrm_check_status == ok_vrm`)
- `license_ok` — license known & usable (green/yellow, not red/unknown)
- `identity_ok` — has a name + an anchor (contract, or CC0/arweave set)

Completeness (for a full, polished set): `banner_ok`, `pfp_ok`, `desc_ok`,
`social_ok`, `count_ok`. `readiness_score` is the count of all 8 (0–8).

## Current state (baseline 2026-08-09)
- Collections mapped: 74 (tiers A/B/C).
- **Hubzz-READY: 1** — RetroDoges.
- Reachable VRMs: 2 `ok_vrm` (RetroDoges, MisfitPIXELS), 3 `reachable_not_vrm`.
- **#1 blocker: `vrm_ok` fails for 72/74** — VRM files are unreachable (dead
  IPFS gateways / hosts). `license_ok` fails for 50; `identity_ok` for 3.

## What the loop does each iteration (`scripts/loop_iterate.sh`)
1. Re-validate reachability of known VRM URLs (catch newly-dead / newly-live).
2. Discover VRM URLs on-chain for collections still missing one.
3. Re-score hubzz readiness.
4. Rebuild the catalog data and commit the refreshed map.

## Strategy to raise the READY count (the real work — see items.json)
- Re-host / re-pin dead VRMs (the 72 `vrm_ok` failures) — biggest lever.
- Fill `license_ok` for the 50 unknown/red licenses (normalize + verify sources).
- Expand sources: Arweave GraphQL sweep, Reservoir/other indexers, discovery leads.

## Human gates
- Adding a NEW collection to the catalog → propose in items.json, human rules.
- Any hubzz ingress of a set → human only. The loop never ingests.
