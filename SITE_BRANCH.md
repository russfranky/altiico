# Altiico site foundation branch

This branch starts from `russfranky/altiico/main` and keeps the existing evidence pipeline intact.

The new website is a separate program under `apps/web`.

Shared browser contracts and UI primitives live under `contracts/` and `packages/`.

The existing Python discovery and validation pipeline remains at the repository root for now.

A later selective migration can move that pipeline under `services/catalog-evidence/` after the product contracts stabilize.

Do not couple React presentation directly to the Python pipeline.

The web application consumes evidence through the catalog port and language-neutral wire contracts.

See `SITE_FOUNDATION.md`, `apps/web/AGENTS.md`, `docs/architecture/UNIX_PHILOSOPHY.md`, and `docs/ledger/LEDGER.md`.
