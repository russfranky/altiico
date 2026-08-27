# ADR 0002 — Brand primitives before feature surfaces
**Status:** Accepted
Create a shared primitive layer before catalog, Studio, or operations feature work.

## Unix philosophy check

- **Single responsibility:** Brand primitives express reusable visual atoms only.
- **Composability:** Feature surfaces compose primitives through the `@altiico/ui` exports.
- **Data boundary:** Primitive props are the typed interface between shared UI and feature composition.
- **Failure behavior:** Feature-specific needs stay local instead of silently changing shared primitive behavior.
- **Simplicity:** A component is promoted only when shared use is proven.
