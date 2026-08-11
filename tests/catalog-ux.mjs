// Structural guardrails for the catalog's reductionist browse surface.
// Run: node tests/catalog-ux.mjs

import { readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "static");
const htmlPath = join(STATIC, "index.html");
const cssPath = join(STATIC, "app.css");
const html = readFileSync(htmlPath, "utf8");
const css = readFileSync(cssPath, "utf8");

let failures = 0;
function assert(condition, message) {
  if (condition) {
    console.log(`  ok:   ${message}`);
  } else {
    failures += 1;
    console.error(`  FAIL: ${message}`);
  }
}

console.log("\n[Catalog UX]");
assert(!html.includes("fonts.googleapis.com"), "uses the system font stack");
assert(!html.includes("fonts.gstatic.com"), "does not preload external fonts");
assert(statSync(cssPath).size < 14_000, "app.css stays below 14 KB");
assert(!/linear-gradient\(|radial-gradient\(/.test(css), "contains no decorative gradients");
assert(!/box-shadow\s*:/.test(css), "contains no drop shadows");
assert(!/backdrop-filter\s*:/.test(css), "contains no backdrop blur");
assert(html.includes('aria-label="Catalog filters"'), "filter surface has an accessible name");
assert(html.includes('aria-live="polite"'), "result count announces updates");
assert(html.includes('class="collection-list"'), "uses a collection list rather than a card grid");
for (const id of ["search", "f-chain", "f-license", "f-vrm", "f-sort", "collectionsGrid", "emptyState", "vrmModal"]) {
  assert(html.includes(`id="${id}"`), `keeps the app.js hook #${id}`);
}
assert(
  css.includes("grid-template-columns: 40px minmax(0, 1fr) auto"),
  "collection rows use one direct grid",
);

console.log(`\n${failures === 0 ? "ALL PASS" : `${failures} FAILURE(S)`}`);
process.exit(failures === 0 ? 0 : 1);
