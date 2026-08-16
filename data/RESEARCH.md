# superyeti — Deep Research: Missing Collections & Data Quality Improvements

**2026-08-17 addendum.** Historical “fully rigged NFT avatar” claims from X
plus A3AC / XR / Bankless archives live in
[`x_rigged_avatar_claims.json`](x_rigged_avatar_claims.json)
([method note](x_rigged_avatar_claims.md)). That file is a claims ledger, not
a verified VRM inventory. jin's
[M3taverse Bookshelf](https://hackmd.io/@XR/book/https%3A%2F%2Fhackmd.io%2F%40xr%2Favatars)
is the same XR series: Part 1 is a 2020 VRM interop primer, Part 3 is the
May 2022 collection survey already cited. VOLTZ is already in the catalog:
public sample is a GLB idle; official VRM is holder-gated. See
[`catalog_research.d/voltz.json`](catalog_research.d/voltz.json).

## Current State

- **65 collections** (Tier A: 25, Tier B: 29, Tier C: 11)
- **216 OpenSea candidates** (6 VRM, 209 no_vrm, 1 not_checked)
- **4,062 avatars** indexed
- **Chains covered**: Ethereum (46), Polygon (4), Base (2), Optimism (1), Shape (1), Multi (2), Unknown (9)
- **Sources**: curated+verified (20), curated (19), a3ac-registry (11), toxsam+curated (7), licensing-index (6), toxsam (2)

### Data Completeness Gaps
| Field | Have | Gap | Priority |
|---|---|---|---|
| license_category | 44% | **CRITICAL** | 1 |
| creator | 30% | **CRITICAL** | 2 |
| max_supply | 23% | **CRITICAL** | 3 |
| vrm_url_https | 10% | Expected (most don't have VRM) | — |
| description | 58% | Medium | 4 |
| discord_url | 53% | Medium | 5 |
| banner_image_url | 70% | Low | 6 |
| total_supply | 76% | Low | 7 |
| release_date | 76% | Low | 8 |
| nft_type | 78% | Low | 9 |
| image_url | 80% | Low | 10 |

---

## Part 1: Missing Collections by Marketplace

### Magic Eden (API available — docs.magiceden.io)

**Solana collections NOT on OpenSea:**
| Collection | Chain | Mint Address | Format | URL |
|---|---|---|---|---|
| EAPES | Solana | `2Dq9kKwK8KRkyjjWUS4Ac5iZ1Y8U64nhqZV4sk8V119v` | 3D (UE5) | eapes3d.com |
| ForgeBots | Solana | (Metaplex) | GLB (rigged) | forgebots.io |
| SOLANA 3D GHOSTS | Solana | — | 3D | magiceden.us/marketplace/solana3dghosts |
| Dinodawgs 3D | Solana | — | 3D (rigged) | magiceden.io/marketplace/dinodawgs_3d |
| Anon Evolved | Solana | — | 3D (dynamic) | howrare.is/anonevolved |
| Baby Ghosts 3D | Solana | — | 3D | nftbirdies.com/drops/sol_3D/ |
| 3D UrbanStyle | Solana | — | 3D (3,340 supply) | nftbirdies.com/drops/sol_3D/ |

**ApeChain collections:**
| Collection | Chain | Contract | Format | URL |
|---|---|---|---|---|
| PAPE | ApeChain | `0xA7aE1BBFA1EE713AcF2A240Cd5Fff184685f5304` | Blender .blend | rulemobile.com |
| GeezOnApe | ApeChain | Deployer: `0x4A5637Cab4563AD6bBe038D8Bd659480Bc01abE3` | 3D rigged | opensea.io/collection/gs-on-ape |
| FUKU | ApeChain | `0x1bcbd0d45d35bbbe514bec8cb9e48c51835a6d8c` | 3D cyberpunk | fukuapes.com |
| Planet XOLO | ApeChain | — | 3D (Otherside) | planetxolo.com |
| Apes On Ape | ApeChain | — | 3D (Otherside) | apesonape.io |

**Base:**
| Collection | Chain | Contract | URL |
|---|---|---|---|
| Virtuals Waifus | Base | `0x631086734a5415f324f4ca350560b56e86c29fdf` | magiceden.io |

### Rarible (API available — docs.rarible.org)
| Collection | Chain | Contract | URL |
|---|---|---|---|
| Moonbirds | Ethereum | `0x23581767a106ae21c074b2276d25e5c3e136a68b` | rarible.com |
| Moonbirds: Mythics | Ethereum | `0xc0ffee8ff7e5497c2d6f7684859709225fcc5be8` | rarible.com |
| VeeFriends Series 2 | Base | `0x324F60bA2d1815EF649DCc73559172305F5dd02c` | rarible.com |

### OKX NFT (API available — web3.okx.com/build/docs)
| Collection | Chain | Contract | URL |
|---|---|---|---|
| mferverse: OG mfers | Ethereum | Base: `0x1142c6fc1fa893b508d5ac3a2d715a61104722e0` | web3.okx.com |
| Flooz GEN F | Ethereum | `0x369156da04b6f313b532f7ae08e661e402b1c2f2` | web3.okx.com |
| Metaverse Stardrop | ApeChain | `0x53e38a3bb5954cc7830bbc6f2520b61d01d95056` | web3.okx.com |

### Other Notable Collections (Ethereum, may be on OpenSea but not in our index)
| Collection | Chain | Contract | Format | URL |
|---|---|---|---|---|
| Non-Fungible People (Daz 3D) | Ethereum | `0x92133e21fff525b16d1edcf78be82297d25d1154` | 3D (8,888) | nfp.daz3d.com |
| Parallel Avatars | Ethereum | `0x0fc3dd8c37880a297166bed57759974a157f0e74` | 3D | blur.io |
| Karafuru 3D | Ethereum | `0xd2F668a8461D6761115dAF8Aeb3cDf5F40C532C6` | 3D (4K) | — |
| Akutars | Ethereum | `0xaad35c2dadbe77f97301617d82e661776c891fa9` | 3D (15K) | opensea.io |
| RUYUI | Ethereum | — | 3D (7K, game-ready) | opensea.io/collection/ruyui |
| Tribe Called Rex | Ethereum | — | 3D (7,500 T-Rex) | tribecalledrex.xyz |
| mferverse: OG mfers | Base | `0x1142c6fc1fa893b508d5ac3a2d715a61104722e0` | 3D | — |

---

## Part 2: Missing Collections by Chain

### Solana (BIGGEST GAP — zero Solana collections in our index)
| Collection | Supply | Format | Notable |
|---|---|---|---|
| EAPES | 3,333 | 3D (UE5) | MultiversX + Solana |
| ForgeBots | 3,333 | GLB (rigged) | Arweave-hosted, Portals-compatible |
| 3D Anvil (platform) | — | VRM + GLB | ToxSam's no-code minting tool for Solana |
| Chain Crisis Specimens | 10,000 | 3D (UE5 game) | In-game avatars |
| AIVerse | — | AI 3D | AR ecosystem |
| Satoshi's Legions | 5,555 | 3D rigged | Cross-chain (ETH→SOL) |

**Scraping approach**: Magic Eden API (requires key application), Helius DAS API for Metaplex data, Solscan API

### Tezos (fxhash marketplace)
| Collection | Supply | Format | URL |
|---|---|---|---|
| fx(avatar) | open ed. | 3D animated | fxhash.xyz/project/fx(avatar) |
| Zpritez 3D | 1,024 | 3D pixel art | fxhash.xyz/generative/slug/zpritez-3d |
| 3D-SMOLSKULLs | 750 | 3D procedural | smolskulls.xyz/3d-smolskull |
| 3D Crypto Cacti | — | 3D rendered | fxhash.xyz |

**Scraping approach**: fxhash API (GraphQL at api.fxhash.xyz)

### Flow (Dapper Labs)
| Collection | Supply | Format | URL |
|---|---|---|---|
| Genies | — | 3D + wearables | genies.com |
| Flovatar | — | 3D (SVG+3D upgrade) | flovatar.com |
| Hoodlums | — | 3D characters | flowverse.co |
| BALLERZ | — | 3D basketball | flowverse.co |
| Driverz | — | 3D racing | flowverse.co |

**Scraping approach**: Flow blockchain API (flow.com/developers), Flowverse directory

### Arbitrum
| Collection | Supply | Contract | URL |
|---|---|---|---|
| ZTX (ZEPETO) | 4,000 | `0x35373efc2fd7d852729cae869cc32acc979100bd` | ztx.io |
| ArbiDudes | 10,000 | `0x1ac7a2fc7f66fa4edf2713a88cd4bad24220c86c` | arbidudes.com |
| Arbibots | 2,000 | `0xc1fcf330b4b4c773fa7e6835f681e8f798e9ebff` | arbibots.xyz (CC0) |

**Scraping approach**: OpenSea API already supports Arbitrum

### Sui
| Collection | Supply | Format | URL |
|---|---|---|---|
| SuiFrens | 350K+ | SVG + dynamic | suifrens.com |
| Prime Machin | 3,333 | 4K + 3D upcoming | prime.nozomi.world |

### Bitcoin Ordinals
| Collection | Supply | Format | URL |
|---|---|---|---|
| BlockForge Identities | 100 | Voxel 3D (WebGPU) | blockforgebtc.com |
| Bitverse | — | 3D via BRC-420 | mybitverse.com |

---

## Part 3: Missing VRM Ecosystem Sources

### Dedicated VRM Marketplaces (NOT in our index)
| Platform | URL | Has API? | Collections |
|---|---|---|---|
| VIPE | vipe.io | Web scrapeable | VIPE Heroes, Grifters Squaddies, 100Avatars |
| Mona | monaverse.com | Yes | User VRM marketplace |
| MEs (O-Me) | o-me.io | Partial | LOOP series, Love & Madness |
| CryptoAvatars | cryptoavatars.io | **Yes** (`api.cryptoavatars.io/v1/opensea/assets/`) | Interoperable VRM avatars |

### Metaverse Platforms with Avatar NFTs
| Platform | URL | Avatar Type | Scrapeable? |
|---|---|---|---|
| The Sandbox | sandbox.game/en/avatars | 3D game avatars | Yes (marketplace pages) |
| Decentraland | decentraland.org | Wearables + VRM export | Yes (documented API) |
| Somnium Space | somniumspace.com | On-chain VR avatars | Yes (OpenSea collection) |
| Gala VOX | collectvox.com | 3D (FBX) avatars | Yes (marketplace) |
| Nifty Island | niftyisland.com | VRM-compatible | Partial |
| Hyperfy | hyperfy.io | VRM + NFT integration | Partial |

### GitHub Registries (easily scrapeable)
| Repo | URL | What it has |
|---|---|---|
| katopz/awesome-vrm | github.com/katopz/awesome-vrm | VRM projects/tools list |
| ToxSam/open-source-avatars | github.com/ToxSam/open-source-avatars | CC0 VRM avatars (JSON data) |
| ToxSam/osa-gallery | github.com/ToxSam/osa-gallery | OpenSourceAvatars.com backend |
| PolygonalMind/100Avatars | github.com/PolygonalMind/100Avatars | 200+ CC0 avatars (VRM/FBX) |
| PabloFMM/numinia-digital-goods | github.com/PabloFMM/numinia-digital-goods | CC0 VRM/GLB assets |

### Emerging Projects to Track
| Project | Chain | Format | URL |
|---|---|---|---|
| Drifters | Base | 3D customizable | tpldrifters.com |
| CLAYPUNKS | — | VRM (VTuber) | claypunks.xyz |
| Holoworld AI (AVA) | Solana | AI 3D agents | holoworld.com |
| PlayerZero | Base | RPM-compatible | playerzero.me |
| Mocaverse | Ethereum | 3D (8,888) | mocaverse.xyz |
| Torque Squad | — | 3D racing (8,888) | torquesquad.io |

### Sources to EXCLUDE
- **VRoid Hub** — explicitly prohibits NFT usage in ToS
- **VRChat Avatar Marketplace** — not NFT-based (proprietary currency)
- **BOOTH.pm** — mostly non-NFT VRChat avatars

---

## Part 4: Data Quality Improvement Plan

### Priority 1: License Data (44% → 75%+)

**Sources:**
1. **NFT Rights Registry** (Google Sheets) — open-source curated list of NFT licenses
   - `docs.google.com/spreadsheets/d/1wkOv_yIwv6SU32I1vIZ7n24_1ZvgMfHbxxhaCTMN00s`
2. **CC0.dev** — searchable database of CC0 NFT projects
3. **Metadata JSON parsing** — check NFT metadata for "license" field
4. **a16z "Can't Be Evil" licenses** — detect in project terms
5. **Manual curation** — check project websites for license terms

**Implementation:**
```python
# check_licenses.py
# 1. Fetch NFT Rights Registry Google Sheet
# 2. Match by contract address or collection name
# 3. Parse NFT metadata for "license" field
# 4. Check cc0.dev for CC0 collections
# 5. Default to "All Rights Reserved" if unknown
```

### Priority 2: Creator Identification (30% → 85%+)

**Sources:**
1. **ERC-2981 royaltyInfo()** — on-chain call returns royalty recipient (proxy for creator)
2. **OpenSea API** — `creator` field in collection data (already fetching, need to extract)
3. **Contract deployer** — first transaction on contract = deployer address
4. **Etherscan labeled addresses** — verified project info (PRO API)
5. **Metadata JSON** — look for "creator" or "artist" field

**Implementation:**
```python
# check_creators.py
# 1. Call royaltyInfo(1, 1000000000000000000) on each contract
# 2. Extract creator from OpenSea collection_details
# 3. Get contract deployer from Etherscan
# 4. Parse metadata for creator/artist fields
# 5. Cross-reference with Etherscan labels
```

### Priority 3: Max Supply (23% → 80%+)

**Sources:**
1. **Contract ABI analysis** — fetch ABI from Etherscan, detect maxSupply functions
2. **Dune Analytics** — SQL query `reservoir.collections.token_count`
3. **Transfer event analysis** — count mint events (Transfer from 0x0)
4. **Moralis NFT API** — `/nft/{address}/stats` returns total_tokens
5. **Alchemy NFT API** — `getContractMetadata` returns totalSupply

**Implementation:**
```python
# check_max_supply.py
# 1. Fetch contract ABI from Etherscan API
# 2. Search ABI for maxSupply/collectionSize/cap/MAX_SUPPLY functions
# 3. Call detected functions via RPC
# 4. Fallback: query Dune for reservoir.collections.token_count
# 5. Fallback: count Transfer(from=0x0) events via Dune/Covalent
```

### Priority 4: Description (58% → 85%+)

**Sources:**
1. **Moralis NFT API** — collection offchain metadata (name, description, image)
2. **Alchemy NFT API** — `getCollectionMetadata` returns description
3. **OpenSea API** — already fetching, ensure we're saving description field
4. **Project website scraping** — meta description tag

### Priority 5: Image Persistence (80% → 95%+)

**Strategy:**
1. **IPFS pinning** — pin all collection images via NFT.storage (free) or Pinata
2. **Arweave** — for permanent storage of key images
3. **Fallback chain**: original URL → ipfs.io gateway → Pinata gateway → Cloudflare gateway → NFTPort cached → placeholder
4. **Local cache** — download images to `os_scrape/images/` directory

**Implementation:**
```python
# cache_images.py
# 1. Download all collection images to local cache
# 2. Pin to IPFS via NFT.storage API
# 3. Store both original URL and cached URL in DB
# 4. HTML uses cached URL with original as fallback
```

---

## Part 5: New API Integrations (ranked by impact)

### Tier 1: Implement Immediately (free, high impact)

| API | Free Tier | Fills Gaps | Key Endpoints |
|---|---|---|---|
| **Dune Analytics** | Free | max_supply, total_supply | SQL queries on `reservoir.collections` |
| **Moralis** | 10K req/day | description, total_supply, creator | `/nft/{address}/stats` |
| **Alchemy** | Free tier | totalSupply, tokenType, metadata | `getContractMetadata` |
| **Reservoir** | Free | mint stages, sales count | `collections/v7?id={contract}` |
| **NFT.storage** | Free | image persistence | IPFS pinning API |

### Tier 2: Implement Next (free with key)

| API | Free Tier | Fills Gaps | Notes |
|---|---|---|---|
| **Magic Eden** | Requires application | Solana collections | docs.magiceden.io |
| **Rarible** | Open API | Cross-chain collections | docs.rarible.org |
| **OKX NFT** | Requires key | ApeChain collections | web3.okx.com/build/docs |
| **NFTScan** | 10K req/day | Multi-chain backup | restapi.nftscan.com |
| **Helius** | Free tier | Solana Metaplex data | DAS API for Solana NFTs |

### Tier 3: Consider Later (paid or limited)

| API | Cost | Fills Gaps | Notes |
|---|---|---|---|
| **Etherscan PRO** | ~$50/mo | creator, social links | Token info endpoint |
| **NFTPort** | ~$49/mo | cached images, rarity | IPFS pinning |
| **Nansen** | Enterprise | Smart Money, labels | Premium analytics |
| **Goldsky** | Enterprise | Real-time streaming | Sub-second latency |

---

## Part 6: Implementation Roadmap

### Phase 1: Fix Critical Gaps (immediate)
1. `check_licenses.py` — NFT Rights Registry + CC0.dev + metadata parsing
2. `check_creators.py` — ERC-2981 royaltyInfo + OpenSea creator field
3. `check_max_supply.py` — ABI analysis + Dune queries
4. Add `description` extraction to existing OpenSea fetch (already have data, not saving it)

### Phase 2: New Chain Coverage
5. `scrape_magiceden.py` — Magic Eden API for Solana/ApeChain collections
6. `scrape_rarible.py` — Rarible API for cross-chain collections
7. `scrape_fxhash.py` — fxhash GraphQL API for Tezos 3D art
8. `scrape_flow.py` — Flow blockchain for Genies, Flovatar, etc.

### Phase 3: VRM Ecosystem
9. `scrape_cryptoavatars.py` — CryptoAvatars API for VRM avatars
10. `scrape_mona.py` — Mona VRM marketplace
11. `scrape_vipe.py` — VIPE marketplace
12. `scrape_sandbox.py` — The Sandbox avatar collections
13. `scrape_decentraland.py` — Decentraland wearables API

### Phase 4: Image & Data Persistence
14. `cache_images.py` — Download + IPFS pin all images
15. `check_image_health.py` — Periodic broken image detection
16. Add data quality scoring to `sy stats`

### Phase 5: Real-time Enrichment
17. Webhook/listener for new collection discoveries
18. Scheduled enrichment runs (cron)
19. Quality score dashboard in HTML

---

## Part 8: scraper-toolkit Integration

The [scraper-toolkit](https://github.com/russfranky/scraper-toolkit) provides
Wayback Machine-based site recovery for dead project websites. Cloned to
`~/src/local/scraper-toolkit`.

### Tools available

| Script | What it does |
|---|---|
| `scripts/recover-site.js` | Generic Wayback recovery for any domain (CDX auto-discovery, 429 backoff) |
| `scripts/recover-images.js` | Recovers Next.js `/_next/image` optimizer URLs from Wayback |
| `scripts/recover-cc.js` | Common Crawl WARC fallback when archive.org rate-limits |
| `toolkit/ssmods.py` | Profile-driven API extraction (cookie-authenticated) |
| `toolkit/capture/` | Headless-Chrome capture of JS-rendered SPAs to self-contained HTML |
| `vipe-archive/` | Already has archived vipe.io pages for ~14 collections |

### Integration with superyeti

1. **`recover_metadata.py`** — Fetches archived HTML from Wayback and extracts
   `og:image`, `og:description` meta tags for collections with dead project URLs.
   Works for static HTML sites. For JS-rendered SPAs, use the scraper-toolkit's
   `capture/` module instead.

2. **`fetch_osavatar_images.py`** — Fetches collection images from the
   ToxSam/open-source-avatars GitHub repo for collections without OpenSea slugs.

3. **`backfill_urls.py`** — Backfills project URLs from A3AC, ToxSam, and
   known sources. Also applies manual image fixes for collections without
   OpenSea images.

### When to use scraper-toolkit directly

- **Full site revival** — When you need to rebuild a dead project website
  (images, CSS, JS, HTML), use `scripts/recover-site.js <domain>`
- **JS-rendered SPAs** — When Wayback's archived HTML doesn't contain meta
  tags (because the site renders everything in JavaScript), use
  `toolkit/capture/capture_page.mjs` to render the archived page in headless
  Chrome and extract the fully-rendered HTML
- **Authenticated scraping** — When you need data behind a login, use
  `toolkit/ssmods.py` with a profile and cookie jar
- **Image recovery** — When you need Next.js optimizer images from Wayback,
  use `scripts/recover-images.js <domain>`

### Dead project URLs (candidates for full recovery)

These collections have dead project websites that could be recovered with
the scraper-toolkit:

| Collection | Domain | Status | Wayback? |
|---|---|---|---|
| CryptoAvatars | cryptoavatars.io | DNS fail | Yes (hijacked) |
| Akutars | akutars.com | DNS fail | No |
| Flooz GEN F | flooz.trade | DNS fail | No |
| MetaTravelers | metatravelers.xyz | DNS fail | No |
| PAPE | pape.xyz | DNS fail | Yes (2018) |
| RSTLSS | rstlss.xyz | DNS fail | Yes (2025) |
| AdWorld | adworld.game | DNS fail | No |
| OG Meta Meeples | lucii.io | DNS fail | Yes (2022) |
| Metaani | conata.world | DNS fail | Yes (2020) |
| ArbiDudes | arbidudes.com | 503 | Yes (2026) |
| Arbibots | arbibots.xyz | SSL fail | Yes (2025) |
| FLUF World | fluf.world | TLS error | Yes (2026) |
| Woodies | woodiesofficial.com | 530 | Yes (2026) |
| Chuddies | scatter.art/chuddies-3d | 404 | Yes (2026) |
| Jadu AVA | jadu.ar/avas | 404 | Yes (2023) |

---

## Part 7: Specific Collections to Add NOW

These are high-confidence 3D avatar collections we're missing that have contract addresses:

| # | Collection | Chain | Contract | Supply | Format | Source |
|---|---|---|---|---|---|---|
| 1 | Non-Fungible People | Ethereum | `0x92133e21fff525b16d1edcf78be82297d25d1154` | 8,888 | 3D (Daz3D) | OpenSea |
| 2 | Parallel Avatars | Ethereum | `0x0fc3dd8c37880a297166bed57759974a157f0e74` | 11,001 | 3D | OpenSea |
| 3 | Akutars | Ethereum | `0xaad35c2dadbe77f97301617d82e661776c891fa9` | 15,000 | 3D | OpenSea |
| 4 | Karafuru 3D | Ethereum | `0xd2F668a8461D6761115dAF8Aeb3cDf5F40C532C6` | 4,000 | 3D | OpenSea |
| 5 | Moonbirds | Ethereum | `0x23581767a106ae21c074b2276d25e5c3e136a68b` | 10,000 | 3D | OpenSea |
| 6 | VeeFriends S2 | Base | `0x324F60bA2d1815EF649DCc73559172305F5dd02c` | — | 3D | Rarible |
| 7 | ZTX Genesis | Arbitrum | `0x35373efc2fd7d852729cae869cc32acc979100bd` | 4,000 | 3D | OpenSea |
| 8 | ArbiDudes | Arbitrum | `0x1ac7a2fc7f66fa4edf2713a88cd4bad24220c86c` | 10,000 | 3D | OpenSea |
| 9 | Arbibots | Arbitrum | `0xc1fcf330b4b4c773fa7e6835f681e8f798e9ebff` | 2,000 | 3D (CC0) | OpenSea |
| 10 | Flooz GEN F | Ethereum | `0x369156da04b6f313b532f7ae08e661e402b1c2f2` | 10,000 | 3D | OKX |
| 11 | mferverse OG | Base | `0x1142c6fc1fa893b508d5ac3a2d715a61104722e0` | — | 3D | OKX |
| 12 | Virtuals Waifus | Base | `0x631086734a5415f324f4ca350560b56e86c29fdf` | — | 3D | Magic Eden |
| 13 | FUKU | ApeChain | `0x1bcbd0d45d35bbbe514bec8cb9e48c51835a6d8c` | 1,111 | 3D | OpenSea |
| 14 | PAPE | ApeChain | `0xA7aE1BBFA1EE713AcF2A240Cd5Fff184685f5304` | — | Blender | OpenSea |
| 15 | Metaverse Stardrop | ApeChain | `0x53e38a3bb5954cc7830bbc6f2520b61d01d95056` | 555 | 3D | OKX |

**Action**: Add these as a new `tier_c_candidates.json` file and import into build_index.py
