# License normalization methodology

This document describes how `scripts/normalize_licenses.py` translates raw
license terms — from embedded VRM metadata, collection-level columns,
external license URLs, and manual curation — into the independent permission
dimensions stored in the `license_dimensions` table (migration 010).

The single source of truth for the mapping is
[`config/license-mapping.yaml`](../config/license-mapping.yaml). Nothing is
hard-coded in Python; to adjust a mapping, edit the YAML and re-run the
normalizer.

## Why dimensions, not buckets

The legacy model stored one coarse `license_category` (green / yellow / red /
unknown) plus free-text columns (`vrm_license`, `commercial_use`,
`allowed_user`, `redistribution`). That collapses several independent
permissions into a single bucket and loses the raw terms that produced it.

The normalized model decomposes the license into nine independent dimensions:

| Dimension | Type | Values |
|---|---|---|
| `use_scope` | text | `everyone` · `holder` · `explicitly_licensed` · `author` · `unknown` |
| `commercial_scope` | text | `none` · `personal_non_profit` · `personal_profit` · `corporation` · `unknown` |
| `credit` | text | `required` · `unnecessary` · `unknown` |
| `redistribute_original` | bool | 0 / 1 / NULL |
| `modify` | bool | 0 / 1 / NULL |
| `redistribute_modified` | bool | 0 / 1 / NULL |
| `corporate_use` | bool | 0 / 1 / NULL |
| `terminates_on_transfer` | bool | 0 / 1 / NULL |
| `hate_speech_termination` | bool | 0 / 1 / NULL |

A boolean `NULL` means "unspecified", not "false". This distinction matters:
"the license does not say" is different from "the license prohibits".

## Precedence

When multiple sources contribute terms for one collection, they are merged in
this order (highest precedence first):

1. **External license URLs** — a recognized Creative Commons or a16z CBE URL
   found in the collection's `project_url`, `sample_metadata_url`, `notes`, or
   `description`. Recognized via `url_patterns` in the mapping YAML.
2. **Collection-level terms** — the legacy `vrm_license` / `commercial_use` /
   `allowed_user` / `redistribution` columns. These are curated project/token
   terms and override embedded metadata.
3. **Embedded VRM meta** — the raw license/permission fields baked into the
   VRM file (migration 007), parsed per VRM spec (0.x or 1.0).
4. **Manual curation** — a pre-existing `license_dimensions` row whose
   `confidence` is `manual`.
5. **Unknown** — no signal at all. Color is `gray`; it is **never** promoted
   to `green`.

Higher-precedence values fill dimensions first; lower-precedence layers fill
only the dimensions that are still unset.

## Conflict handling

When a lower-precedence layer would set a dimension to a *different* non-null
value than a higher-precedence layer already set:

- The higher-precedence value wins and is written to the dimension column.
- `conflict_flag` is set to `1`.
- `LICENSE_CONFLICT` is appended to `reason_codes`, along with a detail code
  naming the dimension and both values, e.g.
  `LICENSE_CONFLICT:redistribute_original=0(collection)_vs_1(embedded[0])`.
- Both raw terms are preserved verbatim in the `raw_*` columns so the conflict
  can be audited and re-resolved manually.

Disagreements between multiple embedded VRM meta blobs (different avatars in
the same collection carrying different license terms) also count as conflicts.

## Confidence

The `confidence` column records the highest-precedence source that
contributed anything:

| Confidence | Meaning |
|---|---|
| `embedded` | Dimensions came from VRM file metadata. |
| `collection` | Dimensions came from collection-level terms or external URLs. |
| `manual` | Only a pre-existing manual row was available. |
| `unknown` | No layer contributed anything. |

The legacy backfill (migration 010) wrote `confidence='legacy'` rows; run
`python scripts/normalize_licenses.py --force` to re-assess them.

## Color derivation

Color is derived from the final dimensions via `color_rules` in the mapping
YAML, evaluated in order — first match wins:

- **green**: `use_scope=everyone` + `redistribute_original=1` + `modify=1` +
  `commercial_scope ∈ {personal_profit, corporation}`.
- **yellow**: any of — holder/explicitly-licensed scope, non-commercial,
  no redistribution, or corporate use.
- **red**: `commercial_scope=none`.
- **gray**: default (unknown / insufficient data).

**Unknown data must never resolve to green.** A rule that requires a concrete
dimension value will not match when that dimension is NULL — that is
intentional. Additionally, a defensive guard inside `assess_collection` forces
`color=gray` (with reason `NEVER_GREEN_FROM_UNKNOWN`) if `confidence=unknown`
somehow produces green, though this cannot happen via the normal flow (no
layers → all dims NULL → gray).

## avatar-use vs file-redistribution

A common source of confusion: the right to *use* an avatar (in a game, social
app, etc.) is separate from the right to *redistribute the VRM file itself*.

- `use_scope` governs who may use the avatar likeness/model.
- `redistribute_original` and `redistribute_modified` govern who may
  re-host, share, or publish the VRM file (original or modified).

A license can grant broad avatar-use rights (e.g. `use_scope=everyone`) while
prohibiting file redistribution (`redistribute_original=0`). The a16z CBE
"Commercial" and "Exclusive" variants are exactly this pattern: holder-scoped
commercial use with redistribution prohibited. This is **not** a conflict —
the two dimensions are independent by design.

## Holder-gated delivery requirement

When `redistribute_original=0` (redistribution prohibited), the VRM file
cannot be served from a public CDN for anyone to download — that would
constitute redistribution. Hubzz must instead deliver the VRM only to
verified token holders via a **signed holder-gated endpoint**:

1. The holder proves token ownership (wallet signature / token-gating proof).
2. Hubzz's backend verifies ownership against the on-chain contract.
3. The VRM URL is issued as a short-lived signed URL, bound to that holder.

Collections where `redistribute_original=1` may be served from a public CDN
without gating. The manifest's `license.redistribute_original` field is the
signal Hubzz uses to decide which path to take.

## VRM 0.x vs 1.0

**VRM 0.x** uses three top-level fields with intentional misspellings
(preserved exactly as written in the spec):

- `allowedUserName` → `use_scope`
- `commercialUssageName` (double-s) → `commercial_scope`
- `licenseName` → full dimension set via the `creative_commons`-style table

Each present field contributes its entry's dimensions; absent fields leave
dimensions unset (NULL).

**VRM 1.0** uses restrictive defaults for any omitted field
(`vrm_1_0.defaults` in the YAML): `onlyAuthor`, `personalNonProfit`,
`required` credit, no redistribution, prohibited modification. Any field
present in the meta overrides the default. This means a VRM 1.0 file with
all license fields omitted resolves to the most restrictive interpretation —
author-only, non-commercial, no redistribution, no modification — which is
yellow (holder/author scope), never green.

## a16z "Can't Be Evil" (6 variants)

| Variant | use_scope | commercial_scope | redistribute | color |
|---|---|---|---|---|
| `PUBLIC` | everyone | corporation | allowed | green |
| `EXCLUSIVE` | holder | corporation | prohibited, terminates on transfer | yellow |
| `COMMERCIAL` | holder | corporation | prohibited | yellow |
| `COMMERCIAL-NO-HATE` | holder | corporation | prohibited, hate-speech termination | yellow |
| `PERSONAL` | holder | none | prohibited | yellow |
| `PERSONAL-NO-HATE` | holder | none | prohibited, hate-speech termination | yellow |

All non-PUBLIC variants are holder-gated and prohibit redistribution —
Hubzz must use signed holder-gated VRM delivery for these.

## Re-running

```sh
# Dry-run (compute, print, no DB writes):
python scripts/normalize_licenses.py --dry-run --force

# Re-assess a single collection:
python scripts/normalize_licenses.py --collection pixelbeasts --force

# Re-assess all collections and write:
python scripts/normalize_licenses.py --force
```

`--force` re-assesses even if a non-legacy row already exists. Without it,
rows with `confidence` other than `legacy` are skipped.
