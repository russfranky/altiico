# Altiico product-site ledger

## Current state

- Phase: `F8 — Bento discovery composition`
- Branch: `product-site-foundation`
- Public main deployment: unchanged
- Last imported standalone checkpoint: `8869f35 / T-007`
- Current turn: `T-008`
- Branch integration commit: `660d5a405d76fd700777ddf34167dd4d75ccbf28`

## Stable decisions

- Set route: `/explore/avatar-sets/[slug]`
- Avatar route: `/explore/avatar-sets/[setSlug]/avatars/[avatarSlug]`
- Product slugs are product-owned.
- Evidence identifiers stay separate.
- Root catalog pipeline stays authoritative for evidence and binary validation.
- Bento composition is approved as a layout direction only.
- Altiico cyan-teal remains the only strong interface accent.

## T-008 completed

- Added the public product site under `product-site/` on the safe integration branch.
- Added a background navigation layer behind the bento composition.
- Applied asymmetrical bento composition to the landing page.
- Applied bento composition to avatar-set discovery.
- Applied bento composition to set detail.
- Applied bento composition to individual-avatar detail.
- Kept the primary robot illustration slot visually dominant.
- Added evidence and identity cells without changing stable product contracts.
- Added task-first mobile collapse rules.
- Kept fixture data explicitly separate from live catalog evidence.

## Public safety

- `main` remains unchanged.
- The current public catalog deployment remains unchanged.
- The evidence pipeline stays at the repository root.
- Product-site deployment cutover requires separate review.

## Next

Verify the product-site build in CI or a preview deployment.

Then add a pinned read-only root-pipeline adapter behind the canonical catalog interface.
