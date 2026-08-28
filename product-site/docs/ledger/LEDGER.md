# Altiico product-site ledger

## Current state

- Phase: `F9 — Visual hierarchy reduction`
- Branch: `product-site-foundation`
- Public main deployment: unchanged
- Last standalone checkpoint: `8869f35 / T-007`
- Current turn: `T-009`

## Stable decisions

- Set route: `/explore/avatar-sets/[slug]`
- Avatar route: `/explore/avatar-sets/[setSlug]/avatars/[avatarSlug]`
- Product slugs are product-owned.
- Evidence identifiers stay separate.
- Root catalog pipeline stays authoritative for evidence and binary validation.
- Bento composition is approved as a layout direction only.
- Altiico cyan-teal remains the only strong interface accent.
- Every bento surface must serve one clear user question or task.
- Evidence should live inside the relevant task surface instead of becoming a dashboard of separate boxes.
- The primary avatar/robot visual should remain one of the largest surfaces on the page.

## T-008 completed

- Integrated the new public product site under `product-site/` on the safe branch.
- Added quiet background navigation behind the bento composition.
- Applied asymmetrical bento composition to landing, discovery, set detail, and avatar detail.
- Kept the primary robot illustration slot visually dominant.
- Added identity, evidence, readiness, traits, and preview cells without changing stable route identity.
- Added task-first mobile collapse rules.
- Kept fixture data explicitly separate from live catalog evidence.
- Added branch-only CI validation with TypeScript, production build, route smoke checks, and desktop/mobile screenshots.
- Fixed the dynamic route segment mismatch discovered by the visual QA workflow.
- Connected a pinned read-only catalog acceptance summary through the adapter boundary.

## T-009 completed

- Reduced the landing page from five bento surfaces to three meaningful surfaces.
- Removed the standalone homepage operations readout and redundant numbered labels.
- Consolidated catalog evidence into the catalog introduction instead of a separate evidence card.
- Removed the static filter foundation panel until filtering has real behavior.
- Consolidated set source, chain, contract, evidence, and license information into one identity strip.
- Reduced set detail to identity, primary visual, and member selection surfaces.
- Consolidated avatar evidence and traits into one detail surface.
- Removed the reserved 3D Studio card; the page now states that preview space should appear only when the viewer is real.
- Simplified the robot stage caption and removed decorative targeting marks.
- Removed decorative corner brackets from every bento cell.
- Reduced footer content to brand plus the core identity-to-presence model.
- Lightened member presentation from nested cards to hairline-linked rows.
- Preserved all product IDs, route contracts, evidence adapters, and pinned evidence behavior.

## Public safety

- `main` remains outside the product-site branch work.
- The current public catalog deployment is not intentionally changed by this branch.
- The evidence pipeline stays at the repository root.
- Product-site deployment cutover requires separate review.

## Next

Review the new reduced desktop/mobile visual QA with the user.

If the hierarchy is approved, do a real illustration and typography polish pass. Import external avatar artwork only after exact asset provenance and reuse terms are recorded.
