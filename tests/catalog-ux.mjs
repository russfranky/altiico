// Structural guardrails for the catalog's reductionist browse surface.
// Run: node tests/catalog-ux.mjs

import { readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "static");
const htmlPath = join(STATIC, "index.html");
const cssPath = join(STATIC, "app.css");
const jsPath = join(STATIC, "app.js");
const overlayPath = join(STATIC, "discovery-overlay.js");
const html = readFileSync(htmlPath, "utf8");
const css = readFileSync(cssPath, "utf8");
const js = readFileSync(jsPath, "utf8");
const overlayJs = readFileSync(overlayPath, "utf8");

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
assert(
  css.includes("overflow-wrap: anywhere"),
  "long evidence URLs wrap cleanly on mobile viewports",
);

let jsParses = true;
try {
  new Function(js);
} catch (error) {
  jsParses = false;
  console.error(`  app.js parse error: ${error.message}`);
}
assert(jsParses, "app.js parses as valid JavaScript");

let overlayParses = true;
try {
  new Function(overlayJs);
} catch (error) {
  overlayParses = false;
  console.error(`  discovery-overlay.js parse error: ${error.message}`);
}
assert(overlayParses, "discovery-overlay.js parses as valid JavaScript");
assert(
  overlayJs.includes("observer.disconnect()") &&
    !/subtree\s*:\s*true/.test(overlayJs) &&
    overlayJs.includes("replaceChildren"),
  "discovery-overlay.js avoids infinite subtree MutationObserver loops",
);

let overlayRuntimeOk = false;
try {
  const createdNodes = [];
  const makeNode = (tag) => {
    const node = {
      tagName: tag.toUpperCase(),
      className: "",
      dataset: {},
      style: {},
      textContent: "",
      title: "",
      children: [],
      attributes: {},
      getAttribute(k) { return this.attributes[k] ?? null; },
      setAttribute(k, v) { this.attributes[k] = String(v); },
      appendChild(c) { this.children.push(c); return c; },
      replaceChildren(...c) { this.children = c; },
      remove() { node._removed = true; },
      querySelector(sel) {
        const cls = sel.startsWith(".") ? sel.slice(1) : null;
        return cls ? this.children.find((c) => c.className === cls) || null : null;
      },
    };
    createdNodes.push(node);
    return node;
  };
  const gridNode = makeNode("div");
  const mainNode = makeNode("div");
  mainNode.className = "crow-main";
  const crowNode = makeNode("article");
  crowNode.className = "crow";
  crowNode.setAttribute("aria-label", "Meebits");
  crowNode.appendChild(mainNode);
  const barNode = makeNode("div");
  barNode.className = "result-bar";
  const obsCalls = [];
  class MockObserver {
    constructor(cb) { this.cb = cb; }
    observe(target, opts) { obsCalls.push({ action: "observe", target, opts }); }
    disconnect() { obsCalls.push({ action: "disconnect" }); }
  }
  const fakeDoc = {
    readyState: "complete",
    createElement: makeNode,
    getElementById: (id) => (id === "collectionsGrid" ? gridNode : null),
    querySelector: (sel) => (sel === ".result-bar" ? barNode : null),
    querySelectorAll: (sel) => (sel === ".crow[aria-label]" ? [crowNode] : []),
    addEventListener() {},
  };
  const sampleRows = [{
    name: "Meebits",
    avatar_delivery_status: "holder_vrm_confirmed",
    evidence_sources: 2,
    evidence_corroborated: 1,
    evidence_conflicts: 0,
    evidence_tokens_sampled: 5,
    evidence_uris_observed: 2,
    evidence_model_signals: 1,
    promotion_candidate_count: 1,
  }];
  vm.runInNewContext(overlayJs, {
    document: fakeDoc,
    console,
    Map,
    Number,
    String,
    MutationObserver: MockObserver,
    fetch: async (path) => ({
      ok: true,
      json: async () => path.includes("build-info")
        ? { files: { collections: "collections.json" } }
        : { collections: sampleRows },
    }),
  });
  await new Promise((r) => setTimeout(r, 20));
  const lastObserve = obsCalls.filter((c) => c.action === "observe").pop();
  const hasDisconnect = obsCalls.some((c) => c.action === "disconnect");
  const decorated = mainNode.children.length === 2 &&
    mainNode.children[0].children[0]?.textContent === "Holder VRM confirmed";
  overlayRuntimeOk = hasDisconnect &&
    lastObserve?.opts?.childList === true &&
    !lastObserve?.opts?.subtree &&
    decorated;
} catch (error) {
  console.error(`  discovery-overlay.js runtime error: ${error.message}`);
}
assert(overlayRuntimeOk, "discovery-overlay.js executes once without subtree observer recursion");

console.log(`\n${failures === 0 ? "ALL PASS" : `${failures} FAILURE(S)`}`);
process.exit(failures === 0 ? 0 : 1);
