// Catalog performance assertions.
//
// P1 spec:
//   - HTML shell < 50KB
//   - initial JSON payload < 500KB compressed (gzip)
//   - JSON.parse + index < 50ms p75
//   - ≤74 collection cards rendered initially
//
// "Initial JSON" = the file app.js fetches on load: collections.
//
// Run: node tests/catalog-performance.mjs
// (pytest doesn't collect .mjs; run directly or wire into CI separately.)

import { readFileSync, readdirSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "static");
const DATA = join(STATIC, "data");

let failures = 0;
function assert(cond, msg) {
  if (!cond) {
    console.error(`  FAIL: ${msg}`);
    failures++;
  } else {
    console.log(`  ok:   ${msg}`);
  }
}

// --- locate content-hashed files (names change when content changes) ---
function find(prefix, suffix) {
  const files = readdirSync(DATA).filter(
    (f) => f.startsWith(prefix) && f.endsWith(suffix),
  );
  if (files.length === 0)
    throw new Error(`no file matching ${prefix}*${suffix} in ${DATA}`);
  return files.map((f) => join(DATA, f));
}

// --- 1. HTML shell size ---
console.log("\n[1] HTML shell size");
const html = readFileSync(join(STATIC, "index.html"));
assert(html.length < 50_000, `index.html < 50KB (got ${(html.length / 1024).toFixed(1)}KB)`);

// --- 2. initial JSON payload compressed ---
console.log("\n[2] initial JSON payload (gzip)");
const collectionFiles = find("collections", ".json");
const initialFiles = [...collectionFiles];
let totalRaw = 0;
let totalGz = 0;
for (const f of initialFiles) {
  const raw = readFileSync(f);
  const gz = gzipSync(raw);
  totalRaw += raw.length;
  totalGz += gz.length;
}
assert(
  totalGz < 500_000,
  `initial JSON gzip < 500KB (got ${(totalGz / 1024).toFixed(1)}KB raw=${(totalRaw / 1024).toFixed(1)}KB)`,
);

// --- 3. JSON.parse + index p75 < 50ms ---
console.log("\n[3] JSON.parse + index p75");
function loadAndIndex(path) {
  const text = readFileSync(path, "utf8");
  const parsed = JSON.parse(text);
  // Build a lookup index by id, mimicking app.js's indexing step.
  const collections = parsed.collections ?? parsed;
  const index = new Map();
  if (Array.isArray(collections)) {
    for (const c of collections) if (c && c.id) index.set(c.id, c);
  }
  return index;
}

const runs = [];
const ITER = 50;
for (let i = 0; i < ITER; i++) {
  const t0 = performance.now();
  for (const f of initialFiles) loadAndIndex(f);
  const t1 = performance.now();
  runs.push(t1 - t0);
}
runs.sort((a, b) => a - b);
const p75 = runs[Math.floor(runs.length * 0.75)];
assert(p75 < 50, `parse+index p75 < 50ms over ${ITER} runs (got ${p75.toFixed(2)}ms)`);

// --- 4. ≤74 cards rendered initially ---
console.log("\n[4] initial card count");
const collectionsJson = JSON.parse(readFileSync(collectionFiles[0], "utf8"));
const cards = collectionsJson.collections ?? collectionsJson;
assert(
  Array.isArray(cards) && cards.length <= 74,
  `≤74 collection cards (got ${Array.isArray(cards) ? cards.length : "not-array"})`,
);
assert(
  Array.isArray(cards) && cards.length > 0,
  `at least 1 collection card (got ${Array.isArray(cards) ? cards.length : 0})`,
);

// --- 5. service worker present and parseable ---
console.log("\n[5] service worker");
import { existsSync, statSync } from "node:fs";
const swPath = join(STATIC, "sw.js");
assert(existsSync(swPath), "static/sw.js exists");
if (existsSync(swPath)) {
  const swSize = statSync(swPath).size;
  assert(swSize < 10_000, `sw.js < 10KB (got ${(swSize / 1024).toFixed(1)}KB)`);
  // Syntax check via new Function (throws on parse error).
  const swSrc = readFileSync(swPath, "utf8");
  let parseOk = false;
  try {
    // Strip the self/addEventListener references by wrapping in a function;
    // we only care that the file parses, not that it runs in Node.
    new Function("self", "caches", "fetch", swSrc);
    parseOk = true;
  } catch (e) {
    console.error(`  sw.js parse error: ${e.message}`);
  }
  assert(parseOk, "sw.js parses as valid JS");
  // Registration snippet must be present in app.js.
  const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
  assert(
    appJs.includes("serviceWorker") && appJs.includes("sw.js"),
    "app.js registers the service worker",
  );
}

// --- summary ---
console.log(`\n${failures === 0 ? "ALL PASS" : `${failures} FAILURE(S)`}`);
process.exit(failures === 0 ? 0 : 1);
