# ADR 0003 — Public homepage and route boundaries
**Status:** Accepted
The homepage explains the system. Feature routes own product behavior.

## Unix philosophy check

- **Single responsibility:** The homepage explains Altiico; feature routes own product behavior.
- **Composability:** Routes share brand and UI primitives without sharing feature responsibilities.
- **Data boundary:** Navigation paths and typed feature contracts connect the explanatory layer to product surfaces.
- **Failure behavior:** Unbuilt routes remain visibly planned rather than pretending to work.
- **Simplicity:** The homepage does not become a dashboard for every Altiico function.
