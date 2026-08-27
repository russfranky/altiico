# Altiico product site

This directory contains the new public-facing Altiico experience.

The evidence pipeline remains at the repository root during integration.

## Architecture boundary

The product site owns presentation, routes, canonical product identity, and typed adapters.

The root pipeline owns research, discovery, binary validation, deterministic snapshots, and staging evidence.

The product site must not infer public identity from contracts, token IDs, source paths, or pipeline slugs.

## Current checkpoint

`T-008 — Discovery bento composition + evidence UI pass`

This branch is safe for review. It does not change the current public deployment on `main`.
