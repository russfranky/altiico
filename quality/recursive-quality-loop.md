# Recursive quality loop

This document tracks the repository-wide feature discovery, test generation, execution, remediation, and regression effort begun on 2026-08-18.

## Iteration 1

- Baseline commit: `8cdf540626a7cca0085e0163ffab986ec62c540b`
- Status: discovery and baseline execution in progress
- Canonical workbook: pending generation under `quality/`
- Known defects before baseline execution:
  - `sy enrich` resolves enrichment scripts from the repository root instead of `scripts/`.
  - `sy build` resolves `build_index.py` and the generated catalog HTML from the repository root instead of `scripts/` and `static/`.

Completion will not be declared until the workbook records the final evidence and all stated exit criteria are met or a remaining risk is explicitly documented.
