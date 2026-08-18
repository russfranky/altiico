# Recursive quality loop

This document tracks the repository-wide feature discovery, test generation, execution, remediation, and regression effort begun on 2026-08-18.

The completed audit lives on `qa/full-codebase-audit-2026-08-18`. Canonical evidence: `quality/Altiico_QA_Canonical.xlsx`.

## Iteration 1 — discovery (PR #38 stub)

- Baseline commit: `8cdf540626a7cca0085e0163ffab986ec62c540b`
- Known defects before baseline execution:
  - `sy enrich` resolves enrichment scripts from the repository root instead of `scripts/`.
  - `sy build` resolves `build_index.py` and the generated catalog HTML from the repository root instead of `scripts/` and `static/`.
- Status: recorded only. No code fix on that branch.

## Iteration 2 — execute and remediate

- Baseline pytest: 385 passed, 3 failed.
- `catalog-ux.mjs`: 2 failures (Google Fonts on `main`).
- `catalog-performance.mjs`: ALL PASS.
- Additional defects found during inventory of `sy`, enrich scripts, OpenPage discovery, short descriptions, and IPFS rewrites (see Defects sheet).

## Iteration 3 — close the loop

- Pytest: **402 passed, 0 failed**.
- UX and performance budgets: **ALL PASS**.
- Remaining waivers: issue #24, issue #36, live OpenSea slug sweep, `sy images` CERT_NONE, no live enrich run without an API key.

Completion is declared for in-repo, credential-free quality. Environmental and identity-research items stay explicit in the workbook.
