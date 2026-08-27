# ADR 0005 — 100Avatars illustration source
**Status:** Accepted

Approve `PolygonalMind/100Avatars` for later illustration imports. Prefer Lalobot as the recurring robot anchor.

## Unix philosophy check
- **Single responsibility:** The source supplies character artwork only.
- **Composability:** Assets enter through existing Altiico provenance rules.
- **Data boundary:** Asset files plus recorded source and license metadata form the interface.
- **Failure behavior:** Missing provenance blocks import.
- **Simplicity:** The source does not introduce a second UI or brand system.
