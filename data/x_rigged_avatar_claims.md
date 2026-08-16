# X + archive claims: historical NFT collections with rigged avatars

This is a **claims ledger**, not a verified-file inventory.

`x_rigged_avatar_claims.json` records 72 collections that X posts, A3AC,
[hackmd/@XR/nftavatars](https://hackmd.io/@XR/nftavatars), or Bankless
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

## Method

X keyword search for `VRM` is noisy (French slang, motherboard VRMs).
This pass used project names + “rigged avatar / VRM / metaverse-ready”
and then corroborated against A3AC and the 2022 XR note. Claims stay in
this ledger until a binary probe admits them to the catalog.
