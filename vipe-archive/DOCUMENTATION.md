# VIPE / Virtual Identity Protocol — Documentation Index

Documentation and reference materials for the vipe.io platform, Virtual Identity Protocol (VIP), and CryptoAvatars ecosystem.

## Archived vipe.io Pages

| Path | Description | Status |
|------|-------------|--------|
| `/about` | About vipe, platform overview | Fetch via wayback |
| `/docs` | Main documentation hub | Fetch via wayback |
| `/help` | Help center | Fetch via wayback |
| `/faq` | Frequently asked questions | Fetch via wayback |
| `/create` | Creator tools entry | Fetch via wayback |
| `/create/avatar` | Avatar creation guide | Fetch via wayback |
| `/create/collection` | Collection creation | Fetch via wayback |
| `/developers` | Developer docs (if exists) | Fetch via wayback |
| `/protocol` | Protocol specification (if exists) | Fetch via wayback |

## docs.vipe.io — API & SDK Reference (from vipe-sdk-unity README)

| Path | Description |
|------|-------------|
| `/` | Docs home |
| `/reference/what-is-the-vipe-unity-sdk` | What is the VIPE Unity SDK? |
| `/reference/getting-started-1` | Getting Started Guide |
| `/reference/developer-integration` | Developer Integration |
| `/reference/example-scene` | Example Scene |
| `/reference/getting-started-with-your-api` | VIPE API Documentation |

Downloaded to `vipe-archive/websites/docs.vipe.io/` when running the script.

**Note:** Wayback captures of docs.vipe.io often return redirects; the script tries a May 2024 timestamp. Live URLs (if still up): https://docs.vipe.io/reference/getting-started-with-your-api

## External Documentation Sources

### Polygonal Mind — Opensource Initiative (CC0)
- **https://github.com/PolygonalMind/initiative-opensource-release**
- **Character packs:** 100 Avatars R1 (2018), R2 (2020), XYZ — VRM/FBX/VXR
- **Asset packs:** Avatar Garden (VRChat, 130 assets), CA World (CryptoAvatars, 65 elements), Cryptoavatars Retro Booth, ABM (Aetherian Block Museum), Avatar Webcam, Chromatic Chaos VHS, Crystal Crossroads, LowPolyStore, Medieval Fair, Momus Park, South DCL, The Avatar Show, Tomb Chaser 1/2
- **The Sandbox:** TSB Megapack (500+), Babylon, Dethrone, Underworld
- 100 Avatars: "First step towards CryptoAvatars"

### Open Source Avatars (ToxSam)
- **https://opensourceavatars.com** — Free VRM registry with direct download links
- **https://github.com/ToxSam/open-source-avatars** — projects.json, avatars/*.json
- Includes: 100Avatars R1/R2/R3, VIPE Heroes, Grifters Squaddies, ToxSam, Halloween Rising, Xmas Chibis, NeonGlitch86

### Awesome 3D Avatar Collections
- **https://github.com/itsmetamike/awesome-3D-avatar-collections** — Curated list of tokenized 3D avatar collections on Ethereum (VRM/GLB metadata params)

### GitHub — VIPE / Avatar SDKs & Docs
| Repo | Description |
|------|-------------|
| **VirtualPersona/vipe-sdk-unity** | Unity SDK for crypto avatars on vipe |
| **CryptoAvatarsOfficial/ca-sdk-unreal** | CryptoAvatars Unreal Engine SDK |
| **cryptoavatars/cryptoavatars.github.io** | CryptoAvatars GitHub Pages (docs) |
| **github.com/virtualsociety** | Virtual Society org (different project: sims/BRP, not avatar-related) |

### CryptoAvatars
- **https://cryptoavatars.io** (defunct) — Original avatar platform (archived to `vipe-archive/websites/cryptoavatars.io/`)
- **https://storage.cryptoavatars.io** — CDN for marketing images (archived)
- Marketing assets indexed in `altiiData.js` (banners, pfps)

### Ethereum / Protocol Contracts
- **VIPE Heroes**: `0x3999877754904d8542ad1845d368fa01a5e6e9a5`
- **Avastars**: `0xF12b5dd48171122709282363198fA019488b14a9`
- **Etherscan**: https://etherscan.io/address/0x3999877754904d8542ad1845d368fa01a5e6e9a5

### Wayback Machine — Key Snapshots
- **vipe.io (Nov 29, 2023)**: https://web.archive.org/web/20231129144808/https://vipe.io/
- **vipe.io (May 30, 2024)**: https://web.archive.org/web/20240530084427/https://vipe.io/
- **vipe.io (Jan 17, 2024)**: explore/collections, assets/avatars
- **vipe.io (Dec 7, 2023)**: styles.css, main.js

### VRM / 3D Avatar Standards
- **VRM specification**: https://vrm.dev/
- VIPE supported VRM for interoperable avatars

## Design Tokens (from vipe.io inline CSS — Apr 2024 capture)

```css
--color-primary: #ffff0b;
--color-vipe-yellow: #ffff0b;
--color-vipe-magenta: #ff34ff;
--color-vipe-green: 114, 255, 60;
--color-vipe-red: #ff3d3d;
--color-vipe-cyan: #3bfffe;
--color-bg-primary: #151515;
--color-bg-secondary: #1a1a1a;
--color-bg-accent: #0d0d0d;
--vipe-gradient: linear-gradient(107.56deg, #191708 0%, #221f64 100%);
--template-columns: 8; /* 7 @ 2560px, 6 @ 1920px, 5 @ 1440px, 4 @ 1280px/1024px, 3 @ 800px, 2 @ 480px, 1 @ 320px */
--frame-margin: 3rem;
--font-silka: "Silka", sans-serif;
--font-scilla: "Scilla", sans-serif;
--font-bulevar: "Bulevar", sans-serif;
```

## In This Archive

After running `npm run wayback:download` (78 URLs total):

| Domain | Contents |
|--------|----------|
| **vipe.io** | HTML pages (script follows 302 redirects to best capture), sitemap.xml, robots.txt, support, contact, blog, press |
| **docs.vipe.io** | API/SDK reference pages |
| **cryptoavatars.io** | Home, docs, about |

- `websites/vipe.io/*.html` — Full wayback playback pages (~150KB each with inline CSS)
- `websites/vipe.io/styles.css` — Raw CSS (manual `curl -sL` if script returns HTML; see README)
- `websites/vipe.io/*.otf` — Silka, Scilla, Bulevar fonts
- `websites/vipe.io/sitemap.xml`, `robots.txt` — SEO assets

**Note:** The script follows HTTP 302 redirects; Wayback often redirects to a different timestamp with the actual capture. Static assets (CSS/JS) may still return HTML when rate-limited; use manual curl for styles.css.

## Revival Context

Altii.co is rebuilding the VIPE heritage. Key concepts:
- **Virtual Identity Protocol** — Avatar interoperability standard
- **Indexed collections** — Curated NFT avatar collections
- **Hubzz** — Target platform for revival
