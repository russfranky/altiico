# VIPE.io Archive Reference

Local copy of vipe.io pages from the Wayback Machine for design recovery reference.

## Download (Node.js script — no Ruby required)

```bash
npm run wayback:download
# or
node scripts/download-wayback.js
```

Downloads pages and assets to `vipe-archive/websites/vipe.io/`:
- **Core:** home, about, connect, privacy, terms, cookie-policy
- **Create:** create, create/avatar, create/collection
- **Explore:** explore, explore/assets/avatars, wearables, animations, explore/collections, explore/community
- **Collection details:** Avastars, CryptoAvatars, VIPE Heroes, Azuki, Bookers, Boomboxheads V2, BAYC, Cryptoadz, 100 Avatars, 3dnotjpegs, SuperYeti, CloneX, Meebits, Forgotten Runes
- **Edit:** explore/collections/avastars/edit
- **Extra:** help, faq, profile, account, docs, brand, the-beeings
- **Documentation:** docs, docs/getting-started, docs/creator-guide, docs/api, docs/vrm, guides, learn, developers, whitepaper, protocol, resources
- **Support/sitemap:** sitemap.xml, robots.txt, support, contact, blog, press
- **docs.vipe.io:** API & SDK reference (6 pages)
- **cryptoavatars.io:** home, docs, about
- **Assets:** styles.css, main.js, runtime.js, polyfills.js, scripts.js
- **Fonts:** Silka, SilkaMono, Scilla, Bulevar (.otf)
- **Images:** favicon.ico, vipe-logo-standard-yellow.png

**Discover mode:** `npm run wayback:discover` — fetches CDX index first to find more URLs (rate-limited).

**Note:** Static assets (CSS, JS, fonts) may return redirects; the script retries with May 2024 timestamp. For best results with styles.css, run:
`curl -sL "https://web.archive.org/web/20240506013928cs_/https://vipe.io/styles.css" -o vipe-archive/websites/vipe.io/styles.css`

## Alternative: wayback-machine-downloader (Ruby)

For a full recursive download:

```bash
gem install wayback-machine-downloader
wayback_machine_downloader https://vipe.io --to 20231129144808
```

## Key design tokens (from vipe.io inline CSS)

```css
--color-primary: #ffff0b;
--color-bg-primary: #151515;
--color-bg-secondary: #1a1a1a;
--template-columns: 8; /* 7 @ 2560px, 6 @ 1920px, 5 @ 1440px, 4 @ 1280px/1024px, 3 @ 800px, 2 @ 480px, 1 @ 320px */
--frame-margin: 3rem;
--font-silka: "Silka", sans-serif;
```

## Documentation Index

See **[DOCUMENTATION.md](./DOCUMENTATION.md)** for a full index of:
- Archived vipe.io doc paths
- External sources (GitHub SDKs: vipe-sdk-unity, ca-sdk-unreal, cryptoavatars.github.io)
- Protocol contracts, design tokens, revival context
