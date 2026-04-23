# altiico — North Star

**Authored:** 2026-04-22
**Status:** Living document — update when scope shifts, not when code changes.
**Owner:** Russ (`russ@thingscorp.com`)

---

## Purpose in one sentence

altiico is the **out-of-engine preview and QA surface** for every avatar, animation, and emote that will eventually appear in the Hubzz 3D virtual world — so nothing ever ships into the world without being seen, measured, and compared against the world's own visual truth.

## Why altiico and not hubzz-admin

hubzz-admin is an **operational dashboard** — it manages production state (spaces, users, roles, collection lifecycle, moderation). It writes. It changes live data.

altiico is a **QA lab** — it reads, renders, compares, and informs decisions. It writes nothing to production. Its job is to let us **see a thing before we commit a thing**. Overloading hubzz-admin with this tooling would bloat it, slow its page loads, and conflate "operate" with "evaluate." Keeping them separate is a deliberate architectural choice.

## The visual truth anchor

Every preview surface in altiico must render in **exactly the same visual conditions** as the Hubzz engine. This is the single most important invariant of the project. If altiico shows something one way and hubzz-client shows it another, altiico is broken — not hubzz.

| Setting | Hubzz engine value | Enforcement |
|---|---|---|
| Camera | `OrthographicCamera` | No perspective ever |
| Camera offset | `Vector3(60, 45, 60)` — canonical isometric | Exported constant |
| Camera target | Avatar feet / tile center `(0, 0, 0)` | lookAt locked |
| Tile size | `TILE_SIZE = 1.0` world unit | Exported constant |
| VRM rotation | `VRMUtils.rotateVRM0(vrm)` — face +Z | Applied on load |
| Ortho frustum | half-height `d = 10` (constant), `left = -d * aspect`, `right = d * aspect`, `top = d`, `bottom = -d`, `near = 0.1`, `far = 1000` | Extracted from `CameraManager.refresh()` |
| Ortho zoom | `camera.zoom = 1.0` at default (not `innerHeight/40` — that was wrong guess) | Exported constant |
| Y-axis convention | +Y up, feet at y=0 | Non-negotiable |
| VRM scale chain | **final = bboxScale × 2.0 × worldEntityScale** where `bboxScale = min(0.7/size.x, 0.7/size.y, 0.7/size.z) * 1.8`. The `× 2.0` comes from `EntityAvatar.ts:640` — do not forget it. worldEntityScale defaults to 1.0. | Matches `EntityAvatar.adjustAvatarScale()` + `EntityAvatar.ts:640` |
| VRM face-camera rotation | `vrm.scene.rotation.y = Math.PI` (non-bot avatars) | Matches `EntityAvatar.ts:331` |
| Prop grid snap | **X/Z always round to whole tile units.** Rotation snaps to 45° increments. | Matches `Entity.moveTo()` behavior (gridSnapping) at engine scale |
| Sandbox-specific note | Sandbox world uses `entityScale: (0.5, 0.5, 0.5)` override. Altiico assumes default `(1, 1, 1)` — if a sandbox-style preview is ever needed, this becomes a toggle. | `sandbox/map.json` |
| Bounding box height | `HUBZZ_SAFE_VOLUME_HEIGHT = 2.0` world units (= 2 tiles wide). Height equals 2×tile-width so the box reads as "2 tiles tall." | north star constant |
| Avatar height target | **1.5m–1.75m** ideal. Rigs outside this range visually clip neighbors. The bounds box gives ~0.25m headroom for hair/hats/head-bob. | product spec |
| Seat height standards | **floor = 0.25m, chair = 0.50m, stool = 0.75m** (altiico values). Hubzz `WorldTile.ts:13` currently has 0.5/1.0/1.5 which are ergonomically wrong — migrate to altiico values before publishing sit-related assets. | altiico proposal → hubzz migration |
| Sitting placement algorithm | **Exact port of hubzz `EntityAvatar.snapToTilePosition` (EntityAvatar.ts:793-811).** Triggered once per animation change (same as hubzz `AvatarAnimationManager.ts:260-262`), not per-frame, not on seat-height change alone. Base: `position.copy(tile.position)` (tile at origin in altiico). If `tile.sittable` and `pelvisBone`: `delta = position - pelvisWorld; position += delta*0.5; position.y += 0.3`. Fallback (no pelvis bone): `position.y -= sitAnim ? hipHeight/3 : 0`. Pelvis bone lookup: `vrm.scene.getObjectByName("Hips")` — NOT `humanoid.getNormalizedBoneNode('hips')`. | hubzz `EntityAvatar.ts:793` |
| Seat height semantics | **Seat height does NOT directly offset the avatar.** It offsets the sittable PROP (couch, chair). Avatar pelvis lands wherever the sit animation puts it + the 0.3 anatomical offset. The prop's seat surface is raised to `HUBZZ_SEAT_HEIGHTS[seatHeight]`, which puts the prop's seat and the avatar's pelvis at the same Y. Matches hubzz editor behavior where sittable assets are placed at the tile's declared seatHeight. | hubzz `EditorAsset.ts:43` |
| Sit facing (sitTarget) | Quarter-turn increments (0/90/180/270°). 0° = camera-facing (hubzz default). Rotation is layered on top of the base π rotation. Mirrors hubzz `sitTarget.lookAt` at EntityAvatar.ts:380-388. | hubzz `EntityAvatar.ts:380` |
| Rig correction scope | Two-tier cascade: **collection default** (shared across all avatars in a collection) + **per-avatar override** (specific to one avatar, beats collection). Resolution order: default (0,0,0) → collection entry → avatar entry. Last write wins within each tier. Engine reads both types from the exported session JSON. | altiico invariant |
| Scope switch with unsaved offset | **Explicit prompt with three choices**: Transfer (keep offset, apply at new scope), Discard (clear offset, switch), Cancel (stay). Fires only when there's a nonzero offset — silent switch otherwise. Prevents accidental collection-wide commits and silent data loss. | altiico UX decision C |

**Bounding box rule:** every avatar must look like it is standing on a single 1×1 tile. Animations that escape the tile's footprint (arms swinging wide, legs kicking out) are visible as a defect — the tile is our intent box. If an animation can't live inside a single-tile bounding volume, it doesn't belong on an idle/walk rig.

## What altiico is allowed to touch

**Read (allowed):**
- `avatar-api` (port 1233) — collection and avatar lists, public endpoints only
- Cloudflare R2 via the public worker (`hubzz-assets-worker.hubzzhq.workers.dev`) — VRM and thumbnail assets
- Any open-source creator drop URLs (OpenSea, Arweave, IPFS) for evaluation before ingest

**Write (forbidden):**
- Never writes to avatars.db, R2 bucket, collections/index.json, or any hubzz-admin state
- Never triggers ingestion, optimization, or publish
- Never mutates user-facing data

**Upload (scoped to the browser session):**
- Local file uploads (VRM drag-and-drop, FBX drag-and-drop) live only in the user's browser memory for that session
- Clicking away discards them — altiico does not persist uploads to any backend

## Scope

### In scope for v1
1. **Isometric preview canvas** — one tile, one VRM, one animation, engine-matching camera
2. **Collection browser** — read-only, pulls from avatar-api, filters by status (staged / published)
3. **Avatar picker** — click an avatar from any collection, load it into the preview canvas
4. **Animation picker** — dropdown of FBX files from a static manifest in `public/animations/`
5. **Animation transport** — play, pause, loop toggle, speed slider, reset
6. **Side-by-side compare** — up to 4 VRMs rendering the same animation in lockstep, same camera pose per quadrant
7. **Local file upload** — test an unpublished VRM or a new FBX in memory before anyone commits them to the repo
8. **Bones / bounds overlay toggles** — skeleton helper, 1×1 tile edges extended up to 2.5m, head-height marker line

### Known deployment constraint

**FBX animation files are served via a dev-box symlink** at `public/animations` → `/root/hubzz-alpha/packages/client/public/models/fbx/`. This works locally but **will 404 in production** because CDNs (Vercel, Cloudflare Pages) don't follow symlinks.

Before deploying altiico to any environment other than this dev box, choose one:

1. **Bake FBX into altiico's `public/animations/`** at build time via a prebuild script (`cp -r` from the hubzz source). Simple, guaranteed to work, but altiico's bundle bloats by ~60MB of FBX data.
2. **Serve FBX from avatar-api or a new endpoint** — altiico's manifest points to absolute URLs (`https://avatar-api.../animations/anim_idle.fbx`). Keeps altiico's bundle tiny. Requires a hubzz-side change (new route + CORS).
3. **Serve from R2** — upload all FBX to Cloudflare R2 with a public prefix; manifest URLs point there. Simplest long-term — matches how avatars are served.

**Recommended: option 3.** R2 already hosts every VRM and thumbnail. Adding `/files/animations/` alongside `/files/avatars/` keeps the asset story coherent and altiico stays static.

### Out of scope for v1 (explicit non-goals)
- ❌ No write operations to any Hubzz system
- ❌ No authentication layer — altiico is a dev/QA tool, gate at the CDN/nginx level if exposed
- ❌ No emote recording or video export (consider v2)
- ❌ No custom animation authoring inside altiico — altiico evaluates, it does not create
- ❌ No AI pose-correction or retargeting magic — we use the same `MixamoLoader.ts` as hubzz-client and accept its limitations
- ❌ No public-facing collection index (that role dies with this revival — hubzz-admin's assets page is the truth)
- ❌ No duplication of hubzz-client as a dependency — `WEBAPP/` subtree is forbidden

## Non-negotiables

1. **No hubzz-admin bloat.** Every feature considered for altiico must fail a "does this belong in hubzz-admin?" test first. If the answer is "kinda, maybe, eventually" — it goes in altiico, not admin.
2. **shadcn/ui only.** No competing design system, no inline styled-components drift, no CSS-in-JS experiments. Reuse the components altiico already ships with.
3. **No new backend.** altiico is static-hostable. Vite build → any CDN. No Node runtime, no database, no queue.
4. **No fork of MixamoLoader.ts.** When hubzz updates its retargeter, altiico picks up the update. Single source of truth for the retargeting math.
5. **Deploy separately from hubzz.** altiico has its own domain (tbd — `altiico.hubzz.xyz` proposed) and its own deploy pipeline. A hubzz outage must not affect altiico and vice versa.
6. **Every avatar it shows is already in avatar-api.** If a collection is not in avatar-api, altiico does not see it. Discovery belongs upstream.

## Success criteria

altiico is working when:

- [ ] Any Hubzz team member can open `altiico.hubzz.xyz/preview`, pick a collection, pick an avatar, pick an animation, and see **exactly** what that avatar will look like in the world — same camera, same tile, same scale — within 3 clicks
- [ ] A person can drag a new FBX onto the page and see it play on 4 different VRMs in a 2×2 grid without leaving the browser
- [ ] A person can confidently say "this animation escapes the tile" or "this rig has stubby arms that look bad with this idle" — and decide whether to reject, fix, or accept, **before** a single byte is committed to `packages/client/public/models/fbx/`
- [ ] hubzz-admin has gained **zero** new surface area from this work
- [ ] altiico's bundle size is < 2MB gzipped (lean enough that it loads fast on throwaway VMs)

## Anti-goals — what altiico is NOT

- **Not a CMS.** It doesn't manage metadata. hubzz-admin owns that.
- **Not a publisher.** It doesn't change collection status. hubzz-admin owns that.
- **Not a minter.** It doesn't touch smart contracts. The blockchain flow belongs in the Privy + NFTManager pipeline.
- **Not a thumbnail generator.** hubzz-admin's `AvatarThumbnailsPage.tsx` owns that.
- **Not a marketplace.** altiico doesn't render storefronts, prices, or sale flows.
- **Not a user-facing product.** altiico is a tool for Hubzz contributors. If a feature needs to exist for end users, it belongs in hubzz-client, not altiico.

## Drift detection — read this before starting any new feature

Before touching altiico code, ask:

1. **Does this feature change production state?** If yes, stop. Belongs in hubzz-admin.
2. **Does this render something users will see in-world?** If yes, it must use the canonical ortho camera + tile + VRM rotation. No exceptions.
3. **Does this duplicate functionality already in hubzz-admin or hubzz-client?** If yes, is that duplication justified by QA isolation? If no, stop — consume the source, don't fork it.
4. **Does this require a new backend, database, or persistence layer?** If yes, stop and re-architect — altiico is static.
5. **Does this add a new dependency?** If the dependency is not already in `package.json`, justify it in writing. Default to "no."

If any answer is "yes" without a crisp, unambiguous justification — the feature doesn't go in altiico.

## Relationship to Hubzz's larger avatar pipeline

altiico sits at the **evaluation stage** of this flow. It never replaces any stage — it sits alongside stage 6.

```
 1. NFT contract    /    open-source creator drop
        ↓
 2. avatar-api ingest (POST /api/collections/:slug/ingest)
        ↓
 3. vrm-optimizer compression (meshopt + texture downscale, preset=aggressive)
        ↓
 4. Cloudflare R2 upload (hubzz-assets-worker)
        ↓
 5. avatars.db updated (optimized_vrm_url)
        ↓
 6. hubzz-admin collection status: draft → ingesting → staged → [altiico preview here] → published → archived
        ↓
 7. In-world: NFTManager + Moralis (wallet path) or getPublishedR2Avatars (default path)
```

**altiico's single job:** make stage 6's "staged → published" transition a confident decision, not a blind commit.

## Camera interaction model

| Behavior | Value |
|---|---|
| Scroll wheel | Adjusts `camera.zoom` between `[0.3, 3.0]`. Cursor-relative (world point under cursor stays fixed). `camera.updateProjectionMatrix()` after each change. |
| Left/middle-click drag on empty space | Pan. Moves `camera.position` via column-0/column-1 of camera matrix, Y component zeroed + normalized. Port of hubzz `InputManager.panLeft / panUp` (InputManager.ts:894-980). |
| No rotation | Camera orientation is permanently locked to the canonical isometric vector `(60, 45, 60)`. Removing OrbitControls was intentional — hubzz has no orbit either. |
| resetCamera() | Sets `camera.position = (60, 45, 60)`, `camera.zoom = 1`, `camera.updateProjectionMatrix()`. |
| Avatar drag | Takes over pointer when user clicks on a VRM mesh child. Camera pan is blocked while avatar drag is active (`panBlocked` prop). |

## Rig-correction offset schema and lifecycle

Every saved correction is a `RigCorrectionEntry` (see `src/lib/rigCorrection.ts`):

```typescript
{
  avatarId: string          // e.g. "100avatars-r1:42"
  collectionSlug: string
  avatarName: string
  animationId: string | null
  seatHeight: 'none' | 'floor' | 'chair' | 'stool'
  facingDeg: number
  offset: { x, y, z }     // world-space delta from snap baseline
  timestamp: string         // ISO
  altiicoVersion: string    // "0.1.0" stub; read from package.json later
}
```

**Lifecycle:**
- Offset accumulates as user drags (baseOffsetRef, updated ~30fps via rAF throttle).
- On change of `avatarUrl`, `animationId`, `seatHeight`, or `facingDeg` — offset is CLEARED and avatar position is reset to snap baseline. A 3-second notice ("Offset cleared — context changed") is shown.
- "Save to session" snapshots the current offset as a `RigCorrectionEntry` (does NOT clear the working offset).
- "Export session" downloads all saved entries as `rig-corrections-<date>.json`. Uses `URL.createObjectURL` + anchor click pattern.
- Session entries already saved are NOT affected by context-change clears.

## Offset clamp bounds

Drag offset is clamped to **±0.5m per axis** (`CLAMP = 0.5` in `AvatarDragHandles.tsx`). When any axis reaches the clamp boundary:
- The ΔX/ΔY/ΔZ chip for that axis turns red (`bg-red-900/40 text-red-300`).
- The rig-correction card gains a red ring (`ring-1 ring-red-500/60`).
- `onClampedChange(true)` fires so the parent can respond.

Clamp applies to the accumulated offset, not per-frame delta — so overshooting still stops at ±0.5m.

## How this document evolves

This north star is **not** a changelog. It records intent, not history. Update it when:
- The scope of altiico materially changes (e.g., a new modality like emote recording is added to v2)
- A non-negotiable is violated and the violation is justified — document the justification
- The relationship to hubzz-admin / hubzz-client / avatar-api changes at the architectural level

Do **not** update it to record:
- Feature work completed (that's the commit log)
- Bug fixes (that's the commit log)
- Design tweaks (that's the PR description)

## Acceptance of this document

This north star is approved for execution when Russ confirms:
- [ ] The purpose sentence is correct
- [ ] The visual truth anchor numbers are correct (tile size 1.0, camera offset `(60, 45, 60)`, ortho zoom formula verified against engine source)
- [ ] The in-scope / out-of-scope lists match the intent
- [ ] The "anti-goals" list matches the intent
- [ ] The pipeline diagram matches the real pipeline (no hallucinated stages)

Until all boxes are checked, no code is written in altiico.

## Related design documents

- `docs/animation-pipeline.md` — full design notes for the avatar animation
  pipeline (Mixamo FBX + Quaternius UAL GLB), including the scalable unified
  pipeline we deliberately did NOT build and the triggers that would justify
  building it. Read this before touching `src/lib/mixamoLoader.ts`,
  `src/lib/ualLoader.ts`, `public/animations/`, or `public/animations.json`.
- `docs/creator-intake.md` — design for the public-facing collection
  submission flow that feeds into `avatar-api ingest`. Not built yet;
  parked pending animation-pipeline work. Captures the legal terms layer,
  status lifecycle, and admin review flow.
