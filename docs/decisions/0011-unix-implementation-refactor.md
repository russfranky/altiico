# ADR 0011 — Enforce Unix philosophy in repository structure
**Status:** Accepted

Split domain types, ports, queries, adapters, runtime selection, integrations, screens, and view components. Add language-neutral wire schemas and focused architecture checks.

## Unix philosophy check
- **Single responsibility:** Each source layer owns one named job.
- **Composability:** Units connect through the catalog port, readonly records, function inputs, and JSON artifacts.
- **Data boundary:** Product records stay typed; service boundaries stay serialized.
- **Failure behavior:** Architecture and behavior checks fail with the exact defect.
- **Simplicity:** The refactor removes mixed modules without adding a state or DI framework.
