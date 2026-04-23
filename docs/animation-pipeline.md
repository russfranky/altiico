# Animation Pipeline — Design Notes

**Last updated:** 2026-04-23
**Status:** POC landed; no cleanup yet

This document captures the full design conversation around the avatar animation
pipeline (altiico + hubzz client) so nothing is lost between sessions. If you
are picking this up cold, read top to bottom.

---

## 1. Where we are today

### Two loaders, two formats, two bone conventions

Both altiico and the hubzz client load avatar animations at runtime. Until now,
everything came from Mixamo:

- **Mixamo FBX** — one file per clip, skeleton embedded in every file
- **Bone naming:** `mixamorigHips`, `mixamorigSpine`, `mixamorigLeftArm`…
- **Loader:** `altiico/src/lib/mixamoLoader.ts` (copied from
  `hubzz-alpha/packages/client/src/engine/misc/MixamoLoader.ts`)
- **Runtime cost:** retargets Mixamo skeleton → VRM humanoid at clip-load time,
  per clip, every session

After the 2026-04-23 POC we now also have:

- **Quaternius UAL1_Standard.glb** — single GLB, 45 named clips, ~7.8 MB total
- **Bone naming:** Unreal Mannequin (`pelvis`, `spine_01`, `upperarm_l`…)
- **License:** CC0 1.0 (public domain, no attribution required)
- **Loader:** `altiico/src/lib/ualLoader.ts` — GLB + Unreal→VRM retargeter
- **Manifest entry:** `source: "ual"`, `clipName: "Idle_Loop"` etc. in
  `public/animations.json`

### Why two loaders is defensible (for now)

The retargeting math is identical — both route every track through
`vrm.humanoid.getNormalizedBoneNode(…)` and produce a `THREE.AnimationClip`.
What differs is only the **input parsing + bone-name table**:

| | Mixamo | UAL |
|---|---|---|
| File format | FBX | GLB |
| Clip naming | one clip per file (`mixamo.com`) | many named clips in one file |
| Bone names | `mixamorigHips` | `pelvis` |
| Network | one request per clip | one request total |

Either loader can be deleted the moment we stop ingesting from that source.
They do not interact; they are ~150 lines each; you can read either in one
sitting.

### POC fixes already applied to `ualLoader.ts`

Three bugs discovered during the POC, all fixed:

1. **Retargeter was reading local `.position.y` of the pelvis** — UAL's
   `root` node carries a −90° X rotation (Unreal Z-up→Y-up conversion) baked
   into the skeleton, so pelvis world-Y is what matters. Fix: call
   `updateWorldMatrix(true, true)` on `asset.scene` before reading, and use
   `getWorldPosition(_vec3).y`.

2. **Scale tracks leaked through** — GLB ships per-bone scale keyframes that
   would distort the VRM rig. Fix: skip any track whose `propertyName ===
   'scale'`.

3. **Root motion was baked into every clip** — UAL clips translate the hips in
   world space (so `Walk_Loop` literally walks the avatar off the tile). Fix:
   drop translation tracks for every bone except `pelvis`, and on `pelvis`
   zero out X/Z so the avatar stays tile-centered (Y is preserved for vertical
   bob on crouch/jump/etc).

### What the POC proved

- Runtime retargeting from Unreal → VRM works.
- 104 of 130 tracks (for `Idle_Loop`) matched the bone table — the 26 skipped
  are legit (scale tracks + bones VRM doesn't care about like `ik_*`).
- Hip-scale resolution on a 0.448 m-hip VRM against UAL's 0.917 m-hip
  skeleton produces `scale=0.488`, which looks correct in-preview.
- No visible quality regression vs. Mixamo on `Idle_Loop`, `Walk_Loop`,
  `Sitting_Idle_Loop`, `Dance_Loop`, `Interact`.

---

## 2. The scalable design (NOT built yet)

This is the design we discussed and **deliberately did not implement** because
simpler shipped today. Preserved here so we don't re-invent it next session.

### One-format, one-loader pipeline

```
hubzz-alpha/
  shared-assets/
    animations/
      source/
        mixamo/                 ← raw FBX inputs (build-time only)
        quaternius/             ← UAL1_Standard.glb source
      build.mjs                 ← converts + merges all sources
      dist/
        animations.glb          ← single runtime artifact
        animations.json         ← clip manifest
```

### What `build.mjs` would do

```
for each source in config:
  load FBX or GLB
  remap bones → VRM humanoid naming (canonical)
  bake retargeting offline (so runtime loader is ~30 lines)
  strip root motion (hips X/Z → 0, Y preserved)
  tag clip { id, category, source, tags, duration }
merge all clips onto one unified skeleton
export dist/animations.glb + dist/animations.json
```

### What it buys

- **One GLB** shared by altiico + hubzz client + admin. One cached network
  fetch unlocks every clip everywhere.
- **One bone convention** (VRM humanoid — since VRM is our runtime target,
  that's the most conventional choice; UAL's Unreal naming was a strawman
  that would require one more translation step at runtime).
- **Zero runtime retargeting** — clips are already VRM-compatible at build
  time, so the runtime loader is trivial.
- **Drop-in new packs** — "add a new animation" = drop FBX into `source/`,
  add entry to build config, run `npm run build:animations`. No code changes
  in either repo.
- **Dead code deletable** — `mixamoLoader.ts` and `ualLoader.ts` both go
  away, replaced by a ~30-line GLB loader.

### How it'd reach both repos

Two acceptable options. Symlinks are **not** on this list — fragile on
Windows, invisible to CI, hide the dependency.

1. **CDN-only (recommended).** `avatar-api` service already has R2 write
   access. Build step outputs `animations.glb` and uploads to
   `files/animations/animations.<hash>.glb`. Both altiico and hubzz client
   fetch from that URL. This is how Unity Addressables / Unreal Pak streaming
   / every live-service web game ships animation content.

2. **Git submodule or npm package.** Works, but heavier ceremony for a two-repo
   team. Only worth it if/when you're shipping multiple versioned packs.

### Why we did NOT build this today

User explicitly said: "The only thing I desperately care about is being
lightweight as possible and keeping it simple enough where we don't get lost
in the sauce." The scalable design is industry-standard but not free:
`build.mjs` is ~200 lines, needs a Blender CLI or `fbx2gltf` dependency for
FBX input, needs a test harness to verify baked retargets don't regress, and
adds a build step to both repos.

Until we hit one of these triggers, the scalable version is premature:

- Shipping **5+ animation packs** and the loaders genuinely diverge
- First-load performance on mobile is measurably hurt by clip-count
- User-uploadable custom emotes
- Multiple teammates need to add animations without touching loader code

---

## 3. The actual next step (when we circle back)

**Audit what animations hubzz production actually uses.** The pruning list
below is NOT authoritative — it's a working inventory. Do not delete anything
without cross-checking each file against:

1. `packages/server/src/Models/Emote.ts` — the DB model's seeded emote list
2. `packages/client/src/engine/entities/avatar/` — EntityAvatar + nearby
   files that call `loadMixamoAnimation` with hardcoded paths
3. `packages/admin/src/components/admin/emotes/` — admin-side emote picker
4. Any `anim_*` or `animation:` string literal in client code

### Inventory of `altiico/public/animations/` (29 FBX + 1 GLB)

Split roughly by category. Columns: **file** | **exposed in altiico picker** |
**suspected hubzz use** (this column requires verification — DO NOT trust it).

**Core locomotion / idle (likely kept):**
- `anim_idle.fbx` — almost certainly shipped in hubzz
- `anim_walk.fbx` — almost certainly shipped
- `anim_jump.fbx` — likely shipped
- `anim_sit.fbx` — almost certainly shipped (entity sit system)

**Gestures (probably shipped as emotes):**
- `anim_waving.fbx` — likely wave emote
- `anim_pray.fbx`
- `anim_rightarm_hold.fbx`
- `anim_angry_raw.fbx`
- `anim_walk_drunk.fbx` — probably dev/test only

**Emotions (status: unclear — may be unused UI-only):**
- `emotion_1_sad.fbx`
- `emotion_2_excited.fbx`
- `emotion_3_defeated.fbx`
- `emotion_4_praying.fbx`
- `emotion_5_joyful.fbx`
- `emotion_6_waiting.fbx`

**Dances (status: unclear — lots of overlap, likely many are unused):**
- `dance_1_sway.fbx` through `dance_9_bboy.fbx`
- `dance_chicken.fbx`, `dance_flair.fbx`, `dance_hh.fbx`,
  `dance_rumba.fbx`, `dance_twerk.fbx`

**Subdirs:** `public/animations/somnia/`, `public/animations/walk3/` —
status completely unknown; inspect before touching.

**Quaternius UAL (added 2026-04-23):**
- `UAL1_Standard.glb` (7.8 MB, 45 clips) — now exposed in altiico picker
  under category `ual`

### Quaternius UAL clip list (full 45)

For cross-referencing when deciding which Mixamo files become redundant:

```
A_TPose                    Pistol_Aim_Down          Spell_Simple_Enter
Crouch_Fwd_Loop            Pistol_Aim_Neutral       Spell_Simple_Exit
Crouch_Idle_Loop           Pistol_Aim_Up            Spell_Simple_Idle_Loop
Dance_Loop                 Pistol_Idle_Loop         Spell_Simple_Shoot
Death01                    Pistol_Reload            Sprint_Loop
Driving_Loop               Pistol_Shoot             Swim_Fwd_Loop
Fixing_Kneeling            Punch_Cross              Swim_Idle_Loop
Hit_Chest                  Punch_Jab                Sword_Attack
Hit_Head                   Push_Loop                Sword_Attack_RM
Idle_Loop                  Roll                     Sword_Idle
Idle_Talking_Loop          Roll_RM                  Walk_Formal_Loop
Idle_Torch_Loop            Sitting_Enter            Walk_Loop
Interact                   Sitting_Exit
Jog_Fwd_Loop               Sitting_Idle_Loop
Jump_Land                  Sitting_Talking_Loop
Jump_Loop
Jump_Start
PickUp_Table
```

Strong UAL coverage for hubzz's likely needs: idle, idle_talking, walk, jog,
sprint, sit enter/idle/exit, sit_talking, dance, wave-ish (Interact), jump,
crouch. Weak coverage for: specific dance variants (bboy, twerk, chicken —
those stay Mixamo), raw emotional poses (sad, excited — those stay Mixamo
unless UAL's Interact covers the intent).

### Audit queries to run before deleting anything

```bash
# From /root/hubzz-alpha — find every place that names an animation file
grep -rn "anim_\|dance_\|emotion_" packages/client/src packages/server/src packages/admin/src | grep -v node_modules | grep -v ".d.ts"

# Check Emote DB seeds
grep -rn "animation\|clip\|url" packages/server/src/Models/Emote.ts
find packages -name "*emote*" -type f | xargs grep -l "anim"

# Check admin emote tab
ls packages/admin/src/components/admin/emotes/
```

Cross-reference anything returned by the greps against the UAL clip list
above. Files that are (a) referenced in hubzz code AND (b) have a UAL
equivalent are prune candidates — replace with the UAL clip ID and test.
Files that are NOT referenced anywhere in hubzz code are safe to delete
outright from altiico's `public/animations/`.

---

## 4. Architectural validation

**Shared humanoid rig + runtime retargeting is the industry-standard pattern
for NFT-aware metaverse avatars.** Major players in the space converge on the
same approach: one canonical skeleton as the runtime target, per-NFT
appearance applied as a texture/mesh layer, universal animations that work
across every avatar because they're all bound to the same rig. hubzz's
VRM-humanoid retargeting strategy matches this pattern.

**Where hubzz differs (intentional advantage):** most competitors are locked
to a single IP (one NFT family, trait variations only). hubzz is
collection-agnostic — any VRM from any creator can be ingested. Do not
sacrifice this flexibility for pipeline cleanliness. The retargeter exists
precisely because we accept arbitrary-skeleton input; that's the moat.

**Future consideration (parked, do not build yet):** a "base rig" avatar for
users without an NFT, paired with trait-overlay layering for owned NFTs
(procedural hat/clothing/fur instead of per-NFT bespoke VRMs). This scales
memory and load time dramatically for users in a known collection, but adds
a trait-authoring pipeline hubzz does not have today. Revisit only if
memory/load time become measurable pain points.

## 5. Quick reference

| Want to… | Do this |
|---|---|
| Preview a UAL clip in altiico | `/preview` → pick avatar → animation picker → UAL category |
| Add a new UAL clip | Edit `altiico/public/animations.json` — add an entry with `source: "ual"` and `clipName: <name from GLB>` |
| Add a new Mixamo clip | Drop FBX into `altiico/public/animations/`, add entry to `animations.json` with no `source` field |
| Verify a UAL clip works in hubzz | Not possible yet — UAL is altiico-only. Requires porting `ualLoader.ts` into `packages/client/src/engine/misc/` |
| Check license compliance | UAL = CC0 (no attribution needed); Mixamo = Adobe Mixamo EULA (check per-use) |

---

## 6. Open questions / follow-ups

- [ ] Audit which Mixamo FBX files are actually referenced in hubzz production
      code. Delete unreferenced files from altiico's `public/animations/`.
- [ ] Decide whether hubzz client should also consume UAL clips. If yes,
      port `ualLoader.ts` into `packages/client/src/engine/misc/UALLoader.ts`.
- [ ] Decide whether to build the unified `animations.glb` pipeline (§2). Only
      pull the trigger when one of the trigger conditions in §2 is hit.
- [ ] Check altiico's `public/animations/somnia/` and `walk3/` subfolders —
      origin and usage unknown.
- [ ] Verify `Sitting_Idle_Loop` y-offset lines up with hubzz's seat heights
      (0.25 / 0.50 / 0.75). Preview looked floaty on chair height during POC.

---

## 7. Licensing sanity

| Source | License | Attribution required | Commercial use |
|---|---|---|---|
| Mixamo | Adobe Mixamo EULA | No | Yes, with Adobe account |
| Quaternius UAL | CC0 1.0 | No | Yes |

UAL is the safer default for any new animation work. Mixamo requires an Adobe
account and the EULA has restrictions on redistribution. If we ever host our
own animation pack on R2 for third-party consumption, **do not include Mixamo
files** without re-checking Adobe's latest terms.
