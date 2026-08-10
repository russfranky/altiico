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

## Current state (iteration 2026-08-10T13:47:53Z)
- Collections mapped: 74 (tiers A/B/C); 4,274 avatar records.
- **Hubzz-READY: 14** — 100Avatars R1/R2/R3, Forgotten Runes Wizards Cult,
  Frutiger Anons, Grifters Squaddies, Halloween Rising, Meebits,
  NeonGlitch86 (Shape side), Phettaverse Editions, RetroDoges, ToxSam,
  VIPE Heroes, Xmas Chibis.
- Reachable VRMs: **19 `ok_vrm`**, 2 `reachable_not_vrm`.
- Blockers: `vrm_ok` fails for 55, `license_ok` for 49, `identity_ok` for 3.
- Unknown VRM location: **21 `no_url`** (down from 33).

> **Corrected 2026-08-10 — do not repeat the earlier conclusion.** A previous
> baseline claimed "72/74 VRMs are dead, IPFS gateway rot, re-hosting required".
> That was WRONG: `extract_vrm_meta.get_range()` sent no User-Agent, so ipfs.io
> and Cloudflare-fronted hosts 403'd the checker. 8 of 12 "dead" URLs returned
> 206 the moment a UA was sent. Most VRMs were never dead. Treat any future
> mass-failure as a client defect until proven otherwise.

## What the loop does each iteration (`scripts/loop_iterate.sh`)
1. Re-validate reachability of known VRM URLs (catch newly-dead / newly-live).
2. Discover VRM URLs on-chain for collections still missing one.
3. Re-score hubzz readiness.
4. Rebuild the catalog data and commit the refreshed map.

## Strategy to raise the READY count (the real work — see items.json)
Ranked by measured yield so far:
1. **`license_ok` (49 failures) is now the biggest lever** — most are `unknown`,
   not genuinely restrictive. Re-assess with `normalize_licenses.py --force` and
   verify sources. NOTE: never auto-promote embedded VRM meta over a confirmed
   collection license — the restrictive triplet is the default VRoid export
   (see docs/vrm-ecosystem.md).
2. **`no_url` (21)** — the on-chain and OpenSea paths are exhausted for these;
   the productive move has been checking data we already hold (the `avatars`
   table's `model_file_url` yielded 5 collections via
   `promote_avatar_vrm_urls.py`).
3. **Genuinely unreachable (~6: timeouts/errors)** — a few are junk URLs where a
   note was stored in the URL field; clean those before assuming rot.
4. Expand sources: Arweave GraphQL sweep, indexer keys, discovery leads.

## Human gates
- Adding a NEW collection to the catalog → propose in items.json, human rules.
- Any hubzz ingress of a set → human only. The loop never ingests.
