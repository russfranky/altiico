# Hubzz and Altiico Integration Architecture

> Status: updated for `HubzzInc/pre-alpha-decomp` downstream consumers (`#32`, `#33`, `#34`, and `russfranky/altiico#43`).
> This repository (`russfranky/altiico`, formerly `russfranky/vrm-catalog`) publishes the read-only VRM Catalog (`https://www.altii.co/`) and produces versioned staging bundles for Hubzz backend ingestion. Superseded references to `russfranky/hubzz-altiico` and browser-side catalog merging are retired.

---

## 1. Domain and Hosting Boundary (`altii.co` vs. `www.altii.co`)

| Host / Path Pattern | Authority | Purpose & Guardrail |
|---|---|---|
| `https://altii.co/{slug}/...` & `/avatars/{slug}/*.vrm` | Cloudflare R2 (`hubzz-assets`, `ALTII_HOST`) | Live canonical Hubzz avatar VRM, `body.png`, `face.png`, and `faces.json` CDN origin. |
| `https://altii.co/` (exact path `/`) | Cloudflare Redirect Rule (`302 -> https://www.altii.co/`) | Only an exact-path rule (`hostname == "altii.co" && uri.path == "/"`) may redirect bare `/` away from R2 `404`. |
| `https://www.altii.co/` | Vercel (`vercel.json` -> `static/`) | Read-only static VRM Catalog (`static/data/*`, free of Hubzz staging badges or pipeline chrome per `SCOPE.md`). |
| `https://avatars.hubzz.app` (`avatar.hubzz.app`) | Nginx on `hubzz-dev` (`HubzzInc/pre-alpha-decomp`) | Pure API and embed host under Option A (`/avatar-api/` `:1233` and `/avatars-index/` `:1234` only; `/`, `/index.html`, `/explore/*` redirect `302` to `https://hubzz.app`). |

**CRITICAL GUARDRAIL:** **NEVER** attach the bare `altii.co` apex domain to Vercel or overwrite its Cloudflare DNS away from the `hubzz-assets` R2 bucket. Redirecting `altii.co` at Vercel or changing non-`/` routes breaks live VRM and imagery assets served under `ALTII_HOST` (`#34`, `altiico#43`).

---

## 2. Responsibilities & Clean Separation

### Producer: `russfranky/altiico` (`www.altii.co`)
- Discovers avatar/NFT collections from OpenSea, Moralis, Etherscan, Bitquery, RPC/indexer surfaces, project metadata, and direct asset URLs.
- Preserves conflicting observations instead of silently overwriting them.
- Validates actual GLB 2.0 binaries (`VRM` or `VRMC_vrm` extensions required for VRM claims; explicit rigging evidence for FBX).
- Maintains a versioned SQLite index (`data/vrm_index.db`) and exports deterministic, snapshot-pinned static artifacts to Vercel (`static/data/avatars-registry.json`, `static/data/hubzz-prealpha-staging.json`, `static/data/hubzz-prealpha-source/*.json`).
- Remains a read-only public research catalog without Hubzz operator pipeline chrome.

### Consumer: `HubzzInc/pre-alpha-decomp`
- **`packages/avatar-ingress` (`:3101`, loopback behind `dash.hubzz.app/ingress-api/*` `requireAdmin`):** Backend staging importer consuming `static/data/hubzz-prealpha-staging.json` and `static/data/hubzz-prealpha-source/*.json` from `altiico`. Dry-run by default (`INGRESS_LIVE` unset).
- **`packages/avatars/api` (`:1233`):** Persists set/avatar records in `/root/pre-alpha-data/avatars.db`, gates writes via service auth token, invokes Hubzz VRM optimizer + canonical R2 uploads under `ALTII_HOST` (`altii.co`), and serves `/avatar-api/*`.
- **`packages/avatars/index` (`:1234`) & `packages/avatars/data`:** Serves avatar discovery metadata and `/avatars-index/embed` for in-world/app surfaces.
- **`packages/avatars/lab` (`studio.hubzz.app`):** Internal rig/asset studio gated behind `AdminGate` + `VITE_LAB_INGEST_TOKEN`, never bypassing backend import/optimization.

---

## 3. Data Flow (Backend Import Only, Zero Browser Coupling)

```text
External discovery sources (OpenSea / Moralis / Etherscan / Bitquery / RPC / IPFS)
  -> altiico evidence pipeline (binary validation + conflict preservation)
  -> static/data/hubzz-prealpha-staging.json + static/data/hubzz-prealpha-source/*.json
  -> Hubzz backend ingest: packages/avatar-ingress (:3101) & avatar-api (:1233)
       - dry-run by default
       - creates staged records only: status = "staged", listed = false
       - preserves provenance, license/review blockers, and conflicts
  -> Hubzz VRM optimizer + canonical R2 publish (https://altii.co/{slug}/... & /avatars/{slug}/*.vrm)
  -> In-world Hubzz client & avatars-index embed surfaces (hubzz.app / avatars.hubzz.app)
```

The browser must never hold GitHub/R2/worker secrets, query blockchain indexers for ingestion, or promote unoptimized external VRMs as canonical served Hubzz assets.

---

## 4. Schema & Import Contract Rules

1. **Identity separation:** Never conflate marketplace identity, contract identity, Hubzz API row id, and on-chain token id.
2. **Staging defaults:** Imported sets from `hubzz-prealpha-staging.json` default to dry-run and write only `status: "staged"`, `listed: false` until operator review and optimization finish.
3. **Provenance and license gates:** Preserve `open` vs. `review`/`gated` license status, conflict flags, and source observation timestamps; existing published Hubzz records are protected from destructive overwrite.
4. **Canonical asset invariant:** Original source URLs remain provenance only; public Hubzz surfaces read optimized assets served through `altii.co` (`ALTII_HOST` R2) with generated `body.png`, `face.png`, `faces.json`, and `baked_scale`.
5. **No SpacetimeDB migration for static catalog evidence:** Keep `data/vrm_index.db` + committed JSON evidence shards in Git + R2/CDN + Vercel static builds for deterministic research catalog snapshots.

---

## 5. Non-Negotiable Evidence Rule

No OpenSea, Moralis, Etherscan, Bitquery, marketplace field, file suffix, or metadata string is sufficient to mark an asset as VRM. Promotion still requires validated GLB 2.0 bytes containing `VRM` or `VRMC_vrm`, plus canonical URI and whole-file hash evidence.
