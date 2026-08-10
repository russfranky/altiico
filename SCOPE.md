# SCOPE — vrm-catalog

Written per the `avoid-feature-creep` framework after an audit found most of the
surface was built for a goal nobody set. Read this before adding anything.

## Core problem
A researcher needs to find VRM avatar collections and answer three questions
fast: **what is this, can I see it, does the file actually work.**

## Success criteria
You can open the page, browse real avatar art, preview any avatar in 3D, and
know whether its VRM file is reachable — without reading a database.

## In scope (v1)
- **Collections** — art, name, description, license, supply, links, VRM status,
  each rolled up with its own avatar-reachability count. One dense list, one view.
- **VRM viewer** — loads any VRM in the browser and shows its embedded metadata.
- **Search** across names, contracts, creators, descriptions.
- **Reachability checking** — collection-level and rolled up from per-avatar checks.
- Four plain-language filters (chain, licence, VRM status, sort) — no research
  state, no annotation. The catalog is read-only.

## Explicitly out of scope
- **Hubzz onboarding / ingestion.** Never asked for. Inventing it produced a
  readiness scorecard, a presence sync, an owner-decision system and a scheduled
  loop. Removed from the interface; the data columns stay, unused, rather than
  risk a destructive migration.
- **Marketplace/registry exports** (`avatar-manifest-v1`, `avatars-registry`).
  Kept as scripts because they are already written and cost nothing to leave
  alone; they are not part of the product and get no UI.
- **Discovery sweeps.** Six vectors returned zero (see
  `docs/discovery-findings.md`). Do not re-run without a new intake source.
- **On-chain tool registries (ERC-8257 / Base).** Explicitly declined.

## Non-negotiables
- No pipeline vocabulary in the interface. `tier A/B/C`, `ok_vrm`,
  `readiness N/8`, `hubzz_status` are internal. Translate them or leave them out.
- Every feature must answer one of the three core questions. If it does not, it
  does not ship.
- Verify by rendering the artifact, not by reading the code.

## What was cut in the 2026-08-10 audit
| Cut | Why |
|---|---|
| "NEW & ready" stat + readiness filter | Serves onboarding, not research |
| Readiness badge (`◐ N/8`, `✅ NEW · ready`) | Internal scoring leaked to the UI |
| Hubzz presence badges (`🏠 in Hubzz`, `◑ partial`) | Onboarding state |
| Declined badge + filter | Existed only to suppress onboarding candidates |
| Tier badge (`Tier A/B/C`) | Pipeline vocabulary; supply + VRM status say more |
| OpenSea Candidates tab | 216 leads, all proven non-VRM — noise |
| Scheduled daily loop | Automation for a goal that no longer exists |
| Avatars tab (4,274-row browser) | Duplicated collection data one row at a time |
| Header stat row (collections/avatars/open/holder/restricted/verified/saved) | Decoration, not a research question |
| Tab bar | One view left; a switch with one position is not a switch |
| Bookmark star, status dropdown, notes | Unused localStorage research-state layer |
| Table view + List/Table toggle | Same fields as the list, denser in the list |
| **Backend for all of the above** — `loadOpensea`/`loadAvatars`/`switchTab`/`sort`/`sortOS` (dead, no callers), `catalog-summary.json` + `opensea-candidates.json` + `avatars-*.json` exports (216 + 4,274 rows nothing fetched), 7 hidden dummy filter `<select>`s | Cutting the UI and leaving the code/data behind it is the same mistake as building the wrong thing — it still ships and still needs reading |
