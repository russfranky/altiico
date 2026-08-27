# ADR 0001 — Workspace foundation
**Status:** Accepted
Use a pnpm workspace with a Next.js application plus shared brand and UI packages.

## Unix philosophy check

- **Single responsibility:** The web app, brand package, and UI package each own one layer.
- **Composability:** Workspace package exports are the narrow interface between layers.
- **Data boundary:** Components and tokens cross package boundaries through ordinary source exports.
- **Failure behavior:** Package or application failures remain isolated to their owning workspace unit.
- **Simplicity:** The workspace avoids one flat application that mixes product routes, design tokens, and reusable primitives.
