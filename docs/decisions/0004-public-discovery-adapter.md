# ADR 0004 — Public discovery uses a typed catalog adapter
**Status:** Accepted

Define `AvatarCatalogPort` as the public discovery data boundary. Use a local fixture adapter during foundation work.

## Unix philosophy check
- **Single responsibility:** The port supplies catalog data; presentation renders it.
- **Composability:** Source adapters can replace each other behind the port.
- **Data boundary:** Typed catalog records cross the boundary.
- **Failure behavior:** Adapter errors remain explicit route states.
- **Simplicity:** Pages do not contain source-specific fetch logic.
