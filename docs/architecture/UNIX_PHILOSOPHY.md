# Unix philosophy for Altiico

Unix philosophy is a repository-wide architecture constraint.

## Core rules

- Do one thing well.
- Compose small parts.
- Keep data interfaces plain and inspectable.
- Separate mechanism from policy.
- Keep state local.
- Make failure visible.
- Prefer replacement over accumulation.
- Avoid captive interfaces.
- Automate with small tools.
- Do not generalize early.

## ADR requirement

Every architecture decision must contain a `## Unix philosophy check` section.

It must address single responsibility, composability, data boundary, failure behavior, and simplicity.

## Enforced implementation

The avatar catalog dependency direction is:

`app routes → runtime → adapters → ports/domain`

`components/screens → domain + queries + presentation helpers + UI`

Domain, ports, queries, and pure integrations cannot perform network I/O or read environment state, browser globals, clocks, or randomness.

Concrete adapter selection happens once in `features/avatar-catalog/runtime/catalog.ts`.

Cross-language evidence data uses JSON Schema under `contracts/catalog-evidence/`.

Product and evidence records are readonly inputs.

Unexpected source failures remain visible through route error boundaries.

Every source module must be reachable from a program or declared library entry point.

Shared UI exports need at least two real application consumers.

Architecture checks must obey their own source-size and single-purpose rules.
