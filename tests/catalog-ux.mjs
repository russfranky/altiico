// Structural guardrails for the catalog's reductionist browse surface.
// Run: node tests/catalog-ux.mjs

import { readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "static");
const htmlPath = join(STATIC, "index.html");
const cssPath = join(STATIC, "app.css");
const jsPath = join(STATIC, "app.js");
const html = readFileSync(htmlPath, "utf8");
const css = readFileSync(cssPath, "utf8");
const js = readFileSync(jsPath, "utf8");

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
assert(statSync(cssPath).size < 12_000, "app.css stays below 12 KB");
assert(!/linear-gradient\(|radial-gradient\(/.test(css), "contains no decorative gradients");
assert(!/box-shadow\s*:/.test(css), "contains no drop shadows");
assert(!/backdrop-filter\s*:/.test(css), "contains no backdrop blur");
assert(html.includes('aria-label="Catalog search and filters"'), "search surface has an accessible name");
assert(html.includes('aria-live="polite"'), "result count announces updates");
assert(html.includes('class="collection-list"'), "uses one collection list");
assert(html.includes('role="list"'), "collection list exposes list semantics");
assert(html.includes('id="filterPanel" class="filter-panel" hidden'), "advanced filters start collapsed");
assert(html.includes('<option value="vrm" selected>Verified first</option>'), "verified collections are the default scan order");
assert((html.match(/role="dialog"/g) || []).length === 1, "keeps only the necessary VRM dialog");
assert(!html.includes("imgModal"), "removes the redundant image-preview modal");
assert(!js.includes("showImg("), "removes image-preview JavaScript");
assert(js.includes("function clearFilters()"), "offers one reset path for search and filters");
assert(
  js.includes("GLB, not VRM") && js.includes("Not a VRM") && !js.includes("Invalid file"),
  "reachable-not-VRM files are labeled as found GLBs, not missing collections",
);
assert(js.includes("aria-hidden"), "keeps viewer visibility explicit to assistive technology");
assert(js.includes("lastFocusedElement"), "returns focus after the viewer closes");
assert(js.includes("if (!window._vrmModalOpen)"), "pauses the 3D render loop when the viewer closes");
for (const id of [
  "search",
  "f-chain",
  "f-license",
  "f-vrm",
  "f-sort",
  "filterToggle",
  "clearFilters",
  "collectionsGrid",
  "emptyState",
  "vrmModal",
]) {
  assert(html.includes(`id="${id}"`), `keeps the app hook #${id}`);
}
assert(
  css.includes("grid-template-columns: 40px minmax(0, 1fr) auto"),
  "collection rows use one direct grid",
);

let jsParses = true;
try {
  new Function(js);
} catch (error) {
  jsParses = false;
  console.error(`  app.js parse error: ${error.message}`);
}
assert(jsParses, "app.js parses as valid JavaScript");

console.log(`\n${failures === 0 ? "ALL PASS" : `${failures} FAILURE(S)`}`);
process.exit(failures === 0 ? 0 : 1);
