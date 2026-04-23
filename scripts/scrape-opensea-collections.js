#!/usr/bin/env node
/**
 * Scrape OpenSea collection pages for metadata (banner, pfp, items, description, contract).
 * Usage: node scripts/scrape-opensea-collections.js
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SLUGS = [
  { slug: 'grillzgang', name: 'Grillz Gang' },
  { slug: 'ganoodles', name: 'Ganoodles' },
  { slug: 'acclimatedmooncats', name: 'Acclimated MoonCats' },
  { slug: 'somzies-somnia', name: 'Somzies (Somnia)' },
];

async function scrapeCollection(page, slug, name) {
  const url = `https://opensea.io/collection/${slug}`;
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForTimeout(6000); // Allow JS to populate

    // Try to extract from __NEXT_DATA__ or similar embedded JSON
    const data = await page.evaluate(({ name: n, slug: s }) => {
      const result = { name: n, slug: s, banner: null, pfp: null, items: null, description: null, contract: null };
      // Meta tags first (often present early)
      const ogImage = document.querySelector('meta[property="og:image"]')?.content;
      if (ogImage) result.banner = result.pfp = ogImage;
      const ogDesc = document.querySelector('meta[property="og:description"]')?.content;
      if (ogDesc) result.description = ogDesc.slice(0, 300);
      const metaDesc = document.querySelector('meta[name="description"]')?.content;
      if (!result.description && metaDesc) result.description = metaDesc.slice(0, 300);
      // All images from seadn or opensea
      const imgs = [...document.querySelectorAll('img[src*="seadn.io"], img[src*="opensea.io"], img[src*="storage.googleapis.com"]')]
        .map(i => i.src).filter(Boolean);
      if (imgs.length > 0 && !result.banner) result.banner = imgs[0];
      if (imgs.length > 1 && !result.pfp) result.pfp = imgs.find(u => u.includes('icon') || u.includes('avatar') || u !== result.banner) || imgs[1];
      if (imgs.length > 0 && !result.pfp) result.pfp = imgs[0];
      // Items - look for stats
      const bodyText = document.body?.innerText || '';
      const itemsMatch = bodyText.match(/([\d,]+)\s*items?/i);
      if (itemsMatch) result.items = itemsMatch[1];
      // Contract
      const links = [...document.querySelectorAll('a[href*="etherscan"]')];
      for (const a of links) {
        const m = a.href.match(/0x[a-fA-F0-9]{40}/);
        if (m) { result.contract = m[0]; break; }
      }
      // Try __NEXT_DATA__ or other embedded JSON
      const nextData = document.getElementById('__NEXT_DATA__')?.textContent;
      if (nextData) {
        try {
          const json = JSON.parse(nextData);
          const pageProps = json?.props?.pageProps ?? {};
          const coll = pageProps?.collection ?? pageProps?.initialData?.collection;
          if (coll) {
            result.banner = result.banner || coll.banner_image_url || coll.image_url || coll.large_image_url;
            result.pfp = result.pfp || coll.image_url || coll.banner_image_url;
            result.description = result.description || coll.description?.slice(0, 300);
            if (coll.stats?.total_supply != null) result.items = String(coll.stats.total_supply);
            if (coll.contracts?.[0]) result.contract = coll.contracts[0].address;
          }
        } catch (_) {}
      }
      return result;
    }, { name, slug });

    // Fallback: try to get images from common OpenSea DOM structure
    if (!data.banner) {
      const imgs = await page.$$eval('img[src*="opensea.io"], img[src*="seadn.io"]', nodes =>
        nodes.map(n => n.src).filter(Boolean)
      );
      if (imgs.length > 0) data.banner = imgs[0];
      if (imgs.length > 1) data.pfp = data.pfp || imgs[1];
    }
    if (!data.items) {
      const itemsText = await page.textContent('body');
      const m = itemsText?.match(/([\d,]+)\s*items?/i);
      if (m) data.items = m[1];
    }
    return data;
  } catch (err) {
    console.error(`Error scraping ${slug}:`, err.message);
    return { name, slug, banner: null, pfp: null, items: null, description: null, contract: null };
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  const page = await browser.newPage();
  await page.setExtraHTTPHeaders({ 'Accept-Language': 'en-US,en;q=0.9' });

  for (const { slug, name } of SLUGS) {
    console.log(`Scraping ${name} (${slug})...`);
    const data = await scrapeCollection(page, slug, name);
    results.push(data);
    await page.waitForTimeout(1500);
  }

  await browser.close();

  const outPath = path.join(__dirname, '../src/data/companionsScraped.json');
  writeFileSync(outPath, JSON.stringify(results, null, 2));
  console.log('Saved to', outPath);
  console.log(JSON.stringify(results, null, 2));
}

main().catch(console.error);
