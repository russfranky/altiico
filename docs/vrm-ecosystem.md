# VRM Ecosystem — Reference and Source Map

Primary-source reference for the VRM format, the tooling that reads it, and the
external registries this catalog can ingest. Field names and enum values below
come from the official spec repo `vrm-c/vrm-specification`. A downstream parser
must key on the exact extension name and byte-for-byte field spellings —
especially the VRM 0.x `...UssageName` misspellings.

## Authoritative sources

| Resource | URL | Role |
|---|---|---|
| VRM specification | https://github.com/vrm-c/vrm-specification | The spec. 0.0 and VRMC_vrm-1.0 schemas + markdown. |
| VRM docs site | https://vrm.dev | Human-readable companion to the spec. |
| UniVRM | https://github.com/vrm-c/UniVRM | Reference implementation (C#/Unity); source of the canonical schema. |

Spec files of record:

- VRM 0.0: `specification/0.0/schema/vrm.meta.schema.json`, `specification/0.0/README.md`
- VRM 1.0: `specification/VRMC_vrm-1.0/schema/VRMC_vrm.meta.schema.json`, `specification/VRMC_vrm-1.0/meta.md`

## 0.x vs 1.0 — how to tell them apart

A `.vrm` is a standard binary glTF (GLB): 12-byte header, then a JSON chunk
(type `0x4E4F534A`), then a BIN chunk. Parse the JSON chunk and read the glTF
root `extensions` object:

- `extensions.VRM` present → **VRM 0.x**. Meta at `extensions.VRM.meta`.
- `extensions.VRMC_vrm` present → **VRM 1.0**. Meta at `extensions.VRMC_vrm.meta`;
  `extensions.VRMC_vrm.specVersion === "1.0"` confirms.
- If both are present, prefer 1.0.

No VRM library is required — any GLB JSON-chunk reader works. This repo's
`scripts/extract_vrm_meta.py` does exactly this with `urllib + struct` and two
HTTP range requests, so no mesh or texture bytes are downloaded.

Companion 1.0 extensions you may also see (not needed for meta):
`VRMC_springBone`, `VRMC_node_constraint`, `VRMC_materials_mtoon`. Standalone
`.vrma` animation files use `VRMC_vrm_animation`.

## Meta fields

### VRM 0.x — `extensions.VRM.meta`

Fields (exact spelling; the doubled-s "Ussage" is intentional and required):
`title`, `version`, `author`, `contactInformation`, `reference`, `texture`
(thumbnail index), `allowedUserName`, `violentUssageName`, `sexualUssageName`,
`commercialUssageName`, `otherPermissionUrl`, `licenseName`, `otherLicenseUrl`.

Enums:

- `allowedUserName`: `OnlyAuthor`, `ExplicitlyLicensedPerson`, `Everyone`
- `violentUssageName` / `sexualUssageName` / `commercialUssageName`: `Disallow`, `Allow`
- `licenseName`: `Redistribution_Prohibited`, `CC0`, `CC_BY`, `CC_BY_NC`,
  `CC_BY_SA`, `CC_BY_NC_SA`, `CC_BY_ND`, `CC_BY_NC_ND`, `Other`

### VRM 1.0 — `extensions.VRMC_vrm.meta`

Required: `name`, `authors` (string array), `licenseUrl`. Other fields:
`version`, `copyrightInformation`, `contactInformation`, `references`,
`thirdPartyLicenses`, `thumbnailImage` (index), `avatarPermission`,
`allowExcessivelyViolentUsage` (bool), `allowExcessivelySexualUsage` (bool),
`commercialUsage`, `allowPoliticalOrReligiousUsage` (bool),
`allowAntisocialOrHateUsage` (bool), `creditNotation`, `allowRedistribution`
(bool), `modification`, `otherLicenseUrl`.

Enums:

- `avatarPermission`: `onlyAuthor`, `onlySeparatelyLicensedPerson`, `everyone`
- `commercialUsage`: `personalNonProfit`, `personalProfit`, `corporation`
- `creditNotation`: `required`, `unnecessary`
- `modification`: `prohibited`, `allowModification`, `allowModificationRedistribution`

> **Field-name traps.** 0.x uses `author` / `title` / `licenseName`; 1.0 uses
> `authors[]` / `name` / `licenseUrl`. 0.x expresses violence/sexual/commercial
> as `Allow`/`Disallow` enums; 1.0 uses booleans (`allowExcessively*Usage`) plus
> the `commercialUsage` enum. `summarize_meta()` in `extract_vrm_meta.py`
> branches on `vrm_spec` for this reason; `config/license-mapping.yaml` carries
> both the `vrm_0x` and `vrm_1_0` sections.

## License semantics

- **0.x** — `licenseName` is a fixed enum that names the whole license; `Other`
  defers to `otherLicenseUrl`. Granular permission is the four coarse enums above.
- **1.0** — `licenseUrl` (required) points to the governing license document
  (VRM 1.0 accepts `https://vrm.dev/licenses/1.0/`); the structured fields
  (`avatarPermission`, `commercialUsage`, `modification`, `creditNotation`, and
  the booleans) configure how it applies. `otherLicenseUrl` and
  `thirdPartyLicenses` hold extra terms.

See `docs/license-methodology.md` for how these map to the normalized
nine-dimension model, and `config/license-mapping.yaml` for the mapping table.

> ### ⚠️ Embedded VRM meta is often an untouched exporter default
> Measured 2026-08-10 by extracting embedded meta from every live VRM in the
> catalog (stored in the `vrm_metadata` table):
>
> | Collection | Embedded license | Reality |
> |---|---|---|
> | **RetroDoges** | `Redistribution_Prohibited / OnlyAuthor / Disallow` | **CC0** (owner-confirmed) |
> | NeonGlitch86 (Shape) | `CC0 / Everyone / Allow` | CC0 — agrees ✅ |
> | MisfitPIXELS | `Redistribution_Prohibited / OnlyAuthor / Disallow` | genuinely restricted |
> | NeonGlitch86 (Polygon) | VRM 1.0 `onlyAuthor / personalNonProfit` | genuinely restricted |
>
> `Redistribution_Prohibited / OnlyAuthor / Disallow` is the **default VRoid
> Studio export**, so it appears on files whose collection is actually open.
> RetroDoges is the proof: its embedded meta contradicts its confirmed CC0.
>
> **Rule:** never auto-promote embedded meta over a confirmed collection-level
> license. Treat embedded meta as *corroborating* evidence — strong when it is
> permissive (an author had to change the default to say CC0), weak when it is
> the restrictive default (indistinguishable from "never configured").

## Tooling (reads/validates VRM meta without a full engine)

| Repo | URL | Note |
|---|---|---|
| pixiv/three-vrm | https://github.com/pixiv/three-vrm | Official three.js loader; `vrm.meta` typed per spec. What a client (Hubzz) uses at runtime. |
| @pixiv/three-vrm-core | (same monorepo) | Lean core incl. meta; best JS reference for the meta types/enums. |
| pygltflib | https://gitlab.com/dodgyville/pygltflib | Pure-Python GLB reader: `GLTF2().load(x).extensions["VRMC_vrm"]["meta"]`. A dependency-light alternative to our stdlib extractor. |
| donmccurdy/glTF-Transform | https://github.com/donmccurdy/glTF-Transform | Node GLB IO; no VRM plugin — read the raw extension object yourself. |
| KhronosGroup/glTF-Validator | https://github.com/KhronosGroup/glTF-Validator | Validates base glTF 2.0 only; treats `VRM`/`VRMC_vrm` as unknown vendor extensions (does NOT validate VRM meta). |

There is no maintained standalone "VRM meta validator"; three-vrm and UniVRM
validate on import. Our own schema/tests are the validation layer for this repo.

## External registries — ingestion map

Ranked by how machine-readable they are for this pipeline.

| Source | Machine-readable? | Status in this repo |
|---|---|---|
| Open Source Avatars (ToxSam) | **Yes** — `data/projects.json` + per-project files on GitHub raw, with commit SHA | **Ingested.** `sources/opensourceavatars.py` already pulls `raw.githubusercontent.com/toxsam/open-source-avatars/main/data/projects.json` with SHA provenance and a 24h cache. |
| awesome-3D-avatar-collections | Partial — curated README list of ~40 NFT VRM collections | **Ingested.** `sources/awesome_3d_avatar_collections.py`. |
| VIPE (vipe.io) | API exists (powers Hyperfy/Upstreet/OnCyber); public schema not published | **Lead** — see `data/discovery_leads.yaml`. VIPE sets are also mirrored inside OSA. |
| VIVERSE Avatar SDK (HTC) | **Yes** — `getPublicAvatarList()` / `getPublicAvatarById()` return objects with a `vrmUrl` field | **Lead** — programmatic, but public avatars are not necessarily NFTs; verify on-chain linkage before ingest. |
| VRoid Hub (pixiv) | API (OAuth) but downloads are creator-gated; ToS blocks NFT use | **Excluded** — policy, recorded in `discovery_leads.yaml`. |
| Ready Player Me | GLB only (not VRM); public API offline since 2026-01-31 | **Not a VRM source.** Do not build on it. |
| BOOTH / Mixamo / VRChat | No VRM export (Mixamo/VRChat) or no API (BOOTH) | Out of scope. |

**Direct manifests worth remembering:**

- OSA index: `https://raw.githubusercontent.com/toxsam/open-source-avatars/main/data/projects.json`
- OSA per-collection: `.../data/avatars/<slug>.json` — each record has
  `model_file_url` (direct VRM), `thumbnail_url`, license, traits. VRM 0.x on
  Arweave/IPFS, mostly CC0.

## Handoff note (Hubzz client)

Hubzz consumes `static/data/avatar-manifest-v1.json` and resolves avatars with
three-vrm at runtime. The manifest's license/access fields are derived from the
normalized dimensions here, so the 0.x-vs-1.0 field mapping above is the
contract boundary: if the extractor mis-reads a 1.0 `licenseUrl` as a 0.x
`licenseName`, the client sees the wrong access mode.
