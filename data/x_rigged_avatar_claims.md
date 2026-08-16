# X + archive claims: historical NFT collections with rigged avatars

This is a **claims ledger**, not a verified-file inventory.

`x_rigged_avatar_claims.json` records 72 collections that X posts, A3AC,
jin's [M3taverse Bookshelf](https://hackmd.io/@XR/book/https%3A%2F%2Fhackmd.io%2F%40xr%2Favatars)
([Avatar Interoperability](https://hackmd.io/@XR/avatars) Mar 2020 →
[NFT 3D Avatars](https://hackmd.io/@XR/nftavatars) May 2022), or Bankless
Metaversal said shipped a fully rigged 3D avatar (VRM, GLB, FBX, or a
holder-gated vault). A tweet or marketplace blurb is **not** a VRM.

## How to read a row

| Field | Meaning |
| --- | --- |
| `verdict` | `shipped` = official delivery documented; `partial` = some files or a shared model; `unverified` = claim only |
| `delivery` | `official-download`, `holder-gated`, `metadata`, `community` |
| `formats` | Claimed or observed formats. `VRM` here is a claim unless the catalog row is `ok_vrm` |
| `catalogSlug` | Existing catalog id when we already have a collection row |

## VOLTZ

Easy to find: [voltz.me](https://voltz.me/),
[OpenSea](https://opensea.io/collection/voltz-avatars), contract
`0xea377cfd0ceab570569d8d37a910071d9e9eb1d4`.

The public CDN sample is a **GLB idle** (`1.glbV01-idle.glb`) with no
`VRM` / `VRMC_vrm` extension. Official VRM + FBX live in the wallet-gated
vault as four archetype files, not one unique VRM per token.

See `catalog_research.d/voltz.json`. Do not mark VOLTZ `ok_vrm` from the
public URL.

## jin / @XR book (this pass)

The URL is a HackMD **book wrapper** around
[hackmd.io/@XR/avatars](https://hackmd.io/@XR/avatars) (Avatar
Interoperability, originally March 2020). It is **not** a second
collection catalog.

| Note | Role |
| --- | --- |
| [Part 1 · Avatars](https://hackmd.io/@XR/avatars) | VRM spec, VRoid, Cryptovoxels `.vox` wearables ported into VRChat, world list (VRChat, Neos, Cluster, Somnium, Webaverse…). Format primer. |
| [Part 2 · LOD](https://hackmd.io/@XR/avatarlod) | Sprite-sheet / imposter optimization. Names Meebits blender utils. |
| [Part 3 · NFT 3D avatars](https://hackmd.io/@XR/nftavatars) | May 2022 collection survey. Already ingested as `web-xr-avatars`. |

Part 1 does **not** add new verified VRM NFT collections. Cryptovoxels
wearables are `.vox` accessories, not full-body VRM inventories. VOLTZ
is absent (minted around the same week as Part 3).

## Method

X keyword search for `VRM` is noisy (French slang, motherboard VRMs).
This pass used project names + “rigged avatar / VRM / metaverse-ready”
and then corroborated against A3AC and the 2022 XR note. Claims stay in
this ledger until a binary probe admits them to the catalog.
