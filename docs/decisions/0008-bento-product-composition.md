# ADR 0008 — Bento product composition
**Status:** Accepted

Adopt the supplied bento image as a composition reference only. Keep the Altiico palette, typography, wordmark, labels, and cyan-teal signal color.

## Unix philosophy check
- **Single responsibility:** Bento rules control page composition only.
- **Composability:** Cells compose existing feature components and primitives.
- **Data boundary:** Cells receive normal props and records.
- **Failure behavior:** Responsive collapse preserves accessible order.
- **Simplicity:** The decision avoids a second brand or nested card explosion.
