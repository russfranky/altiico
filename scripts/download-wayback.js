#!/usr/bin/env node
/**
 * Download archived vipe.io site from Wayback Machine.
 * No Ruby/gem required - uses Node.js https.
 *
 * Usage: node scripts/download-wayback.js [--discover]
 *   --discover  Fetch CDX index first to find more URLs (rate-limited)
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import https from 'https';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TIMESTAMP = '20231129144808';
const ALT_TIMESTAMP = '20231207234418';
const ASSET_TIMESTAMP = '20240506013928';
const DOCS_TIMESTAMP = '20240530084427';
/** Alternate timestamps when Nov 2023 returns redirects (from user archive refs) */
const EXPLORE_TS = '20240117205556';  // explore/collections, assets
const ASSETS_TS = '20240621032017';  // explore/assets/avatars
const TIMESTAMPS_HTML = [TIMESTAMP, EXPLORE_TS, ASSETS_TS, ALT_TIMESTAMP];
const ARCHIVE_ROOT = path.join(__dirname, '..', 'vipe-archive', 'websites');
const CDX_DISCOVER = process.argv.includes('--discover');

/** { path, url, outDir? } — outDir defaults to vipe.io */
const URLS_TO_FETCH = [
  // Core
  { path: '/', url: 'https://vipe.io/' },
  { path: '/about', url: 'https://vipe.io/about' },
  { path: '/connect', url: 'https://vipe.io/connect' },
  // Create
  { path: '/create', url: 'https://vipe.io/create' },
  { path: '/create/avatar', url: 'https://vipe.io/create/avatar' },
  { path: '/create/collection', url: 'https://vipe.io/create/collection' },
  // Explore
  { path: '/explore', url: 'https://vipe.io/explore' },
  { path: '/explore/assets/avatars', url: 'https://vipe.io/explore/assets/avatars' },
  { path: '/explore/collections', url: 'https://vipe.io/explore/collections' },
  { path: '/explore/community', url: 'https://vipe.io/explore/community' },
  // Collection details (from CDX + altiiData)
  { path: '/explore/collections/avastars', url: 'https://vipe.io/explore/collections/avastars' },
  { path: '/explore/collections/cryptoavatars', url: 'https://vipe.io/explore/collections/CryptoAvatars' },
  { path: '/explore/collections/vipe-heroes', url: 'https://vipe.io/explore/collections/VIPE%20Heroes' },
  { path: '/explore/collections/azuki', url: 'https://vipe.io/explore/collections/azuki' },
  { path: '/explore/collections/bookers', url: 'https://vipe.io/explore/collections/bookers' },
  { path: '/explore/collections/boomboxheads-v2', url: 'https://vipe.io/explore/collections/boomboxheads-v2' },
  { path: '/explore/collections/bored-ape-yacht-club', url: 'https://vipe.io/explore/collections/bored-ape-yacht-club' },
  { path: '/explore/collections/cryptoadz-by-gremplin', url: 'https://vipe.io/explore/collections/cryptoadz-by-gremplin' },
  { path: '/explore/collections/100-avatars', url: 'https://vipe.io/explore/collections/100%20Avatars' },
  { path: '/explore/collections/3dnotjpegs', url: 'https://vipe.io/explore/collections/3dnotjpegs' },
  { path: '/explore/collections/superyeti', url: 'https://vipe.io/explore/collections/SuperYeti' },
  { path: '/explore/collections/clonex', url: 'https://vipe.io/explore/collections/CloneX' },
  { path: '/explore/collections/meebits', url: 'https://vipe.io/explore/collections/Meebits' },
  { path: '/explore/collections/forgotten-runes', url: 'https://vipe.io/explore/collections/Forgotten%20Runes' },
  // Asset types (avatars, wearables, animations)
  { path: '/explore/assets/wearables', url: 'https://vipe.io/explore/assets/wearables' },
  { path: '/explore/assets/animations', url: 'https://vipe.io/explore/assets/animations' },
  // Assets
  { path: '/styles.css', url: 'https://vipe.io/styles.css' },
  { path: '/main.js', url: 'https://vipe.io/main.js' },
  { path: '/runtime.js', url: 'https://vipe.io/runtime.js' },
  { path: '/polyfills.js', url: 'https://vipe.io/polyfills.js' },
  { path: '/scripts.js', url: 'https://vipe.io/scripts.js' },
  // Fonts (vipe custom)
  { path: '/Silka-Regular.otf', url: 'https://vipe.io/Silka-Regular.otf' },
  { path: '/Silka-Medium.otf', url: 'https://vipe.io/Silka-Medium.otf' },
  { path: '/Silka-Bold.otf', url: 'https://vipe.io/Silka-Bold.otf' },
  { path: '/SilkaMono-Regular.otf', url: 'https://vipe.io/SilkaMono-Regular.otf' },
  { path: '/Scilla-Regular.otf', url: 'https://vipe.io/Scilla-Regular.otf' },
  { path: '/Bulevar-Regular.otf', url: 'https://vipe.io/Bulevar-Regular.otf' },
  // Images & icons
  { path: '/favicon.ico', url: 'https://vipe.io/favicon.ico' },
  { path: '/vipe-logo-standard-yellow.png', url: 'https://vipe.io/vipe-logo-standard-yellow.png' },
  // Legal / footer
  { path: '/privacy', url: 'https://vipe.io/privacy' },
  { path: '/terms', url: 'https://vipe.io/terms' },
  // Edit flow (from avastars link)
  { path: '/explore/collections/avastars/edit', url: 'https://vipe.io/explore/collections/avastars/edit' },
  // Cookie policy (from cookie banner)
  { path: '/cookie-policy', url: 'https://vipe.io/cookie-policy' },
  // Additional routes
  { path: '/help', url: 'https://vipe.io/help' },
  { path: '/faq', url: 'https://vipe.io/faq' },
  { path: '/profile', url: 'https://vipe.io/profile' },
  { path: '/account', url: 'https://vipe.io/account' },
  { path: '/docs', url: 'https://vipe.io/docs' },
  { path: '/brand', url: 'https://vipe.io/brand' },
  { path: '/the-beeings', url: 'https://vipe.io/explore/collections/the-beeings' },
  // Documentation (keep digging)
  { path: '/docs/getting-started', url: 'https://vipe.io/docs/getting-started' },
  { path: '/docs/creator-guide', url: 'https://vipe.io/docs/creator-guide' },
  { path: '/docs/api', url: 'https://vipe.io/docs/api' },
  { path: '/docs/vrm', url: 'https://vipe.io/docs/vrm' },
  { path: '/guides', url: 'https://vipe.io/guides' },
  { path: '/learn', url: 'https://vipe.io/learn' },
  { path: '/developers', url: 'https://vipe.io/developers' },
  { path: '/whitepaper', url: 'https://vipe.io/whitepaper' },
  { path: '/protocol', url: 'https://vipe.io/protocol' },
  { path: '/resources', url: 'https://vipe.io/resources' },
  // Sitemap, robots, support
  { path: '/sitemap.xml', url: 'https://vipe.io/sitemap.xml' },
  { path: '/robots.txt', url: 'https://vipe.io/robots.txt' },
  { path: '/support', url: 'https://vipe.io/support' },
  { path: '/contact', url: 'https://vipe.io/contact' },
  { path: '/blog', url: 'https://vipe.io/blog' },
  { path: '/press', url: 'https://vipe.io/press' },
];

/** docs.vipe.io (from vipe-sdk-unity README) — API, Unity SDK, reference */
const DOCS_VIPE_URLS = [
  { path: '/', url: 'https://docs.vipe.io/', outDir: 'docs.vipe.io' },
  { path: '/reference/what-is-the-vipe-unity-sdk', url: 'https://docs.vipe.io/reference/what-is-the-vipe-unity-sdk', outDir: 'docs.vipe.io' },
  { path: '/reference/getting-started-1', url: 'https://docs.vipe.io/reference/getting-started-1', outDir: 'docs.vipe.io' },
  { path: '/reference/developer-integration', url: 'https://docs.vipe.io/reference/developer-integration', outDir: 'docs.vipe.io' },
  { path: '/reference/example-scene', url: 'https://docs.vipe.io/reference/example-scene', outDir: 'docs.vipe.io' },
  { path: '/reference/getting-started-with-your-api', url: 'https://docs.vipe.io/reference/getting-started-with-your-api', outDir: 'docs.vipe.io' },
];

/** cryptoavatars.io — related avatar protocol (storage.cryptoavatars.io in altiiData) */
const CRYPTOAVATARS_URLS = [
  { path: '/', url: 'https://cryptoavatars.io/', outDir: 'cryptoavatars.io' },
  { path: '/docs', url: 'https://cryptoavatars.io/docs', outDir: 'cryptoavatars.io' },
  { path: '/about', url: 'https://cryptoavatars.io/about', outDir: 'cryptoavatars.io' },
];

function fetchUrl(url, redirectCount = 0) {
  const MAX_REDIRECTS = 5;
  return new Promise((resolve, reject) => {
    https
      .get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' } }, (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          const data = Buffer.concat(chunks);
          if (redirectCount < MAX_REDIRECTS && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            const loc = res.headers.location;
            const next = loc.startsWith('http') ? loc : new URL(loc, url).href;
            fetchUrl(next, redirectCount + 1).then(resolve).catch(reject);
          } else {
            resolve(data);
          }
        });
      })
      .on('error', reject);
  });
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/** Detect redirect/429/404 HTML (wayback often returns these instead of real content) */
function isRedirectOrError(data) {
  if (data.length < 600 && Buffer.isBuffer(data)) {
    const s = data.toString('utf8', 0, 500);
    return /Redirecting|429|Too Many Requests|Not Found|404/i.test(s) || (s.includes('<html') && s.includes('</body>'));
  }
  return false;
}

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', (c) => (data += c));
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          reject(new Error('Invalid JSON'));
        }
      });
    }).on('error', reject);
  });
}

async function discoverFromCDX() {
  const cdxUrl = 'https://web.archive.org/cdx/search/cdx?url=vipe.io/*&output=json&filter=statuscode:200&from=20231101&to=20231231&collapse=urlkey&matchType=prefix';
  console.log('Discovering URLs from CDX (may be rate-limited)...\n');
  await sleep(2000);
  try {
    const rows = await fetchJson(cdxUrl);
    if (!rows || rows.length < 2) return [];
    const urlIdx = rows[0].indexOf('original');
    const seen = new Set([...URLS_TO_FETCH, ...DOCS_VIPE_URLS, ...CRYPTOAVATARS_URLS].map((u) => u.url));
    const extra = [];
    for (let i = 1; i < rows.length; i++) {
      const original = rows[i][urlIdx];
      if (!original?.startsWith('https://vipe.io/') || seen.has(original)) continue;
      const queryIdx = original.indexOf('?');
      const pathPart = queryIdx > 0 ? original.slice(0, queryIdx) : original;
      if (pathPart === 'https://vipe.io/') continue;
      const filePath = pathPart.replace('https://vipe.io', '') || '/';
      if (filePath.includes('/tab=') || /\d{2,}$/.test(filePath)) continue;
      seen.add(original);
      extra.push({ path: filePath, url: original });
    }
    return extra.slice(0, 30);
  } catch (err) {
    console.log('  CDX discovery failed:', err.message);
    return [];
  }
}

async function main() {
  let urlsToFetch = [...URLS_TO_FETCH, ...DOCS_VIPE_URLS, ...CRYPTOAVATARS_URLS];
  if (CDX_DISCOVER) {
    const discovered = await discoverFromCDX();
    urlsToFetch = [...urlsToFetch, ...discovered];
    console.log(`Found ${discovered.length} extra URLs from CDX\n`);
  }

  console.log(`Downloading vipe.io + docs.vipe.io archive (timestamp: ${TIMESTAMP}) to ${ARCHIVE_ROOT}\n`);
  fs.mkdirSync(ARCHIVE_ROOT, { recursive: true });

  for (const { path: filePath, url, outDir: customOutDir } of urlsToFetch) {
    const outDir = path.join(ARCHIVE_ROOT, customOutDir || 'vipe.io');
    const ext = path.extname(filePath).toLowerCase();
    const isAsset = /\.(css|js|otf|png|ico|jpg|jpeg|webp|svg)$/.test(ext);
    const prefix = ext === '.css' ? 'cs_' : ext === '.js' ? 'js_' : isAsset ? 'im_' : 'if_';
    const isExplore = filePath.startsWith('/explore');
    const isExploreAssets = filePath.startsWith('/explore/assets');
    const baseTs = customOutDir === 'docs.vipe.io' ? DOCS_TIMESTAMP
      : customOutDir === 'cryptoavatars.io' ? '20230922060200'
      : isAsset ? ASSET_TIMESTAMP
      : isExploreAssets ? ASSETS_TS
      : isExplore ? EXPLORE_TS
      : TIMESTAMP;
    const tsList = isAsset ? [ASSET_TIMESTAMP, ALT_TIMESTAMP] : (customOutDir === 'docs.vipe.io' ? [DOCS_TIMESTAMP] : TIMESTAMPS_HTML);
    let archiveUrl = `https://web.archive.org/web/${baseTs}${prefix}${url}`;
    const fileName = filePath === '/' ? 'index.html' : filePath.replace(/^\//, '') + (ext || path.extname(filePath) ? '' : '.html');
    const outPathFinal = path.join(outDir, fileName || 'index.html');
    fs.mkdirSync(path.dirname(outPathFinal), { recursive: true });

    try {
      let data = await fetchUrl(archiveUrl);
      if (data.length === 0 || (data.length < 600 && !isAsset && isRedirectOrError(data))) {
        for (const retryTs of tsList.slice(0, 4)) {
          if (retryTs === baseTs) continue;
          archiveUrl = `https://web.archive.org/web/${retryTs}${prefix}${url}`;
          await sleep(400);
          data = await fetchUrl(archiveUrl);
          if (data.length > 600 || (!isRedirectOrError(data) && data.length > 0)) break;
        }
      }
      fs.writeFileSync(outPathFinal, data);
      const size = data.length;
      console.log(`  ✓ ${outPathFinal.replace(ARCHIVE_ROOT + path.sep, '')}${size === 0 ? ' (0B)' : ''}`);
    } catch (err) {
      console.log(`  ✗ ${filePath} (${err.message})`);
    }
    await sleep(350);
  }

  console.log('\nDone. Browse: vipe-archive/websites/vipe.io/');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
