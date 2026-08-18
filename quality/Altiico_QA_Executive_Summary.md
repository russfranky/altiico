# Altiico QA Executive Summary

**Date:** 2026-08-18
**Baseline:** `8cdf540626a7cca0085e0163ffab986ec62c540b` (`main`)
**Branch:** `qa/full-codebase-audit-2026-08-18`
**Canonical record:** [`quality/Altiico_QA_Canonical.xlsx`](Altiico_QA_Canonical.xlsx) (also `Altiico_QA_Canonical.csv`)

This pass applied the QA audit package to [russfranky/altiico](https://github.com/russfranky/altiico). The attached stub workbook had headers only; the live tree was inventoried, tested, and remediated against the actual implementation.

## Verdict

The catalog's evidence pipeline and public browse surface are in good shape. The unified CLI and a handful of enrichment scripts had drifted from the `scripts/` + `data/` layout and would have mutated the wrong database if anyone followed `sy enrich` / `sy build` as documented.

After this branch:

| Gate | Main (baseline) | This branch |
| --- | --- | --- |
| `pytest tests/` | 385 passed, **3 failed** | **402 passed, 0 failed** |
| `node tests/catalog-ux.mjs` | **2 failures** (Google Fonts) | **ALL PASS** |
| `node tests/catalog-performance.mjs` | ALL PASS | ALL PASS |

Live snapshot counts: **69 collections**, **152 avatars**, **216 OpenSea candidates**. Figures in `AGENTS.md` (74 / 4,062) are stale documentation, not live defects.

## What was fixed

1. **`sy enrich` / `sy build` path bugs** — scripts and HTML resolved from the repo root instead of `scripts/` and `static/`. Failures now exit nonzero. Linux uses `xdg-open`.
2. **`sy show` identity** — exact name/id/slug/contract wins over `LIKE '%q%'`.
3. **Enrichment scripts** — `check_supply`, `check_traits`, `check_discord`, `check_opensea_urls`, `fetch_previews` now target `data/vrm_index.db` and lazy-load the OpenSea key (import no longer crashes without `~/.opensea/api_key`).
4. **Google Fonts** removed from the public shell so `catalog-ux.mjs` matches the documented system-font contract.
5. **Short descriptions** keep a complete first sentence even when it is shorter than half the card budget.
6. **OpenPage candidates** dedupe by URL and upgrade `openpage_record` → `mml_inline` → `mml_fetched`.
7. **Stale registry test** no longer treats All Rights Reserved as `purchase_gated`. File-access gating stays independent of IP (already implemented; test was wrong).
8. **IPFS HTTPS rewrite** uses `ipfs.io`, not the shut-down Cloudflare public gateway.

## Remaining, explicit

| Item | Why it is still open |
| --- | --- |
| [Issue #24](https://github.com/russfranky/altiico/issues/24) | CyberBrokers PFP identity vs Genesis Mechs sample evidence. Report-only audit exists; no automatic rebind. |
| [Issue #36](https://github.com/russfranky/altiico/issues/36) | GitHub protection / Dependency Graph / secret scanning. Not flip-able from this app. |
| Live OpenSea slug sweep | Needs `~/.opensea/api_key`. Offline slug-collision class already fixed historically. |
| `sy images` `ssl.CERT_NONE` | Accepted local research-tool risk. |
| Enrichment live run | Scripts are now correctly wired; this environment has no OpenSea key, so they were not executed against the network. |
| Draft PRs #35 / #37 / #38 | Hardening, scrape-recall, and the earlier quality-loop stub. This branch is the completed audit on current `main`, not a merge of those PRs. |

## Exit criteria

- [x] Canonical workbook filled from the live tree
- [x] Generated tests executed
- [x] Defects with in-repo fixes remediated and regression-covered
- [x] Remaining risks named, not papered over
- [x] Branch published to GitHub
