# ADR 0009 — Discovery data convergence and precedence
**Status:** Accepted

Add a pure convergence layer between legacy evidence snapshots and canonical product records. Preserve product IDs, public slugs, API IDs, display copy, publish state, and readiness.

## Unix philosophy check
- **Single responsibility:** The convergence layer maps evidence only.
- **Composability:** Pure functions connect snapshot records to product records.
- **Data boundary:** Serializable snapshots and readonly product records cross the boundary.
- **Failure behavior:** Snapshot and reconciliation conflicts remain explicit.
- **Simplicity:** Convergence performs no network I/O, rendering, publication, or ID generation.
