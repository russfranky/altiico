// ─── Data loading (lazy, content-hashed JSON files) ──────────────────────────
let DATA = { collections: [] };
let BUILD_INFO = null;

async function fetchJSON(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`Failed to load ${path}: ${resp.status}`);
  return resp.json();
}

async function loadBuildInfo() {
  BUILD_INFO = await fetchJSON('data/build-info.json');
  return BUILD_INFO;
}

async function loadCollections() {
  const info = BUILD_INFO || await loadBuildInfo();
  const data = await fetchJSON('data/' + info.files.collections);
  DATA.collections = data.collections || [];
  filter();
}

// ─── Shared helpers ─────────────────────────────────────────────────────────
let _collRows = [];

function esc(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : ''; }
function badge(cls, text) { return `<span class="badge badge-${cls}">${esc(text)}</span>`; }

function licenseBadge(cat, c) {
  // Colour comes from the traffic-light category; the text is the ACTUAL licence
  // name when we have one. Previously both were rendered, so the colour badge sat next to
  // a second "CC0" badge saying the same thing.
  const generic = { green: 'Open', yellow: 'Holder', red: 'Restricted', unknown: 'Unknown' }[cat] || 'Unknown';
  const real = (c && c.vrm_license || '').trim();
  const label = real || generic;
  if (!c) return badge(cat || 'unknown', label);
  const rc = c.reason_codes || [];
  const conf = c.license_confidence || 'unknown';
  const parts = [label];
  if (rc.length) parts.push(rc.join(', '));
  parts.push(`[${conf}]`);
  return `<span class="badge badge-${cat || 'unknown'}" title="${esc(parts.join(' — '))}">${esc(label)}</span>`;
}

function supplyText(c) {
  if (!c.total_supply) return null;
  const ms = c.mint_status;
  const note = ms === 'ongoing' ? ' (minting)' : '';
  return `${c.total_supply.toLocaleString()}${note}`;
}

// Block explorer per chain — every contract link used to point at etherscan.io,
// which is simply wrong for the 16 collections that are not on Ethereum.
const EXPLORERS = {
  ethereum: ['https://etherscan.io/address/', 'Etherscan'],
  base: ['https://basescan.org/address/', 'BaseScan'],
  polygon: ['https://polygonscan.com/address/', 'PolygonScan'],
  optimism: ['https://optimistic.etherscan.io/address/', 'Optimistic Etherscan'],
  arbitrum: ['https://arbiscan.io/address/', 'Arbiscan'],
  shape: ['https://shapescan.xyz/address/', 'ShapeScan'],
  ape_chain: ['https://apescan.io/address/', 'ApeScan'],
  zora: ['https://explorer.zora.energy/address/', 'Zora Explorer'],
};

function explorerFor(chain, addr) {
  const e = EXPLORERS[(chain || '').toLowerCase()];
  return e ? { url: e[0] + addr, name: e[1] } : null;
}

// Where the VRM actually lives, derived from the verified URL.
function storageOf(c) {
  const u = c.vrm_check_url || c.vrm_url_https || c.vrm_url_pattern || '';
  if (!u) return null;
  const low = u.toLowerCase();
  const cid = /\/ipfs\/([A-Za-z0-9]+)/.exec(u);
  if (low.startsWith('ipfs://') || cid) {
    return { kind: 'IPFS', icon: '', href: cid ? 'https://ipfs.io/ipfs/' + cid[1] : u,
             detail: cid ? cid[1] : u };
  }
  const ar = /arweave\.net\/([A-Za-z0-9_-]{43})/.exec(u);
  if (ar || low.startsWith('ar://')) {
    const tx = ar ? ar[1] : u.slice(5);
    return { kind: 'Arweave', icon: '', href: 'https://viewblock.io/arweave/tx/' + tx, detail: tx };
  }
  if (low.includes('githubusercontent') || low.includes('github.com'))
    return { kind: 'GitHub', icon: '', href: u, detail: u };
  try { return { kind: new URL(u).hostname.replace(/^www\./, ''), icon: '', href: u, detail: u }; }
  catch { return null; }
}

function collLinks(c) {
  const out = [];
  if (c.opensea_slug) out.push(`<a class="icon-link" href="https://opensea.io/collection/${encodeURIComponent(c.opensea_slug)}" target="_blank" rel="noopener" title="OpenSea">OS</a>`);
  if (c.project_url) out.push(`<a class="icon-link" href="${esc(c.project_url)}" target="_blank" rel="noopener" title="Website">Web</a>`);
  if (c.twitter_username) out.push(`<a class="icon-link" href="https://twitter.com/${esc(c.twitter_username)}" target="_blank" rel="noopener" title="@${esc(c.twitter_username)}">X</a>`);
  if (c.discord_url && c.discord_status === 'alive') out.push(`<a class="icon-link" href="${esc(c.discord_url)}" target="_blank" rel="noopener" title="Discord">DC</a>`);
  return out.join('');
}

// Contract + storage, shown as readable chips rather than a mystery icon.
function chainChips(c) {
  const out = [];
  const contracts = (c.contracts && c.contracts.length)
    ? c.contracts
    : (c.contract ? [{ address: c.contract, chain: c.chain }] : []);
  for (const ct of contracts.slice(0, 2)) {
    const addr = ct.address; if (!addr) continue;
    const ex = explorerFor(ct.chain || c.chain, addr);
    const short = addr.slice(0, 6) + '…' + addr.slice(-4);
    out.push(ex
      ? `<a class="chip chip-link" href="${esc(ex.url)}" target="_blank" rel="noopener" title="${esc(addr)} — open on ${esc(ex.name)}">${esc(short)}</a>`
      : `<span class="chip" title="${esc(addr)} — no explorer configured for ${esc(ct.chain || c.chain || 'this chain')}">${esc(short)}</span>`);
  }
  const st = storageOf(c);
  if (st) out.push(`<a class="chip chip-link" href="${esc(st.href)}" target="_blank" rel="noopener" title="VRM files stored on ${esc(st.kind)} — ${esc(st.detail)}">${esc(st.kind)}</a>`);
  return out.join('');
}


// ─── Filtering + collection rendering ────────────────────────────────────────
let _filterTimer = null;
function onSearch() {
  clearTimeout(_filterTimer);
  _filterTimer = setTimeout(filter, 150);
}

function applyCollectionFilters() {
  const q = document.getElementById('search').value.toLowerCase();
  const fChain = document.getElementById('f-chain').value;
  const fLicense = document.getElementById('f-license').value;
  const fVrm = (document.getElementById('f-vrm') || {}).value || '';
  let rows = DATA.collections.filter(c => {
    if (fChain && c.chain !== fChain) return false;
    if (fLicense && (c.license_category || 'unknown') !== fLicense) return false;
    if (fVrm === 'live' && c.vrm_check_status !== 'ok_vrm') return false;
    if (fVrm === 'dead' && c.vrm_reachable !== 0) return false;
    if (fVrm === 'nourl' && c.vrm_check_status !== 'no_url') return false;
    if (q) {
      const hay = [c.name, c.contract, c.opensea_slug, c.vrm_license, c.creator, c.notes, c.description, c.curated_description, c.vipe_category].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const sortSel = (document.getElementById('f-sort') || {}).value || 'name';
  const VRM_RANK = { ok_vrm: 0, reachable_not_vrm: 1, no_url: 3 };
  rows.sort((a, b) => {
    if (sortSel === 'vrm') return (VRM_RANK[a.vrm_check_status] ?? 2) - (VRM_RANK[b.vrm_check_status] ?? 2)
                                || String(a.name).localeCompare(String(b.name));
    if (sortSel === 'release_date') return String(b.release_date || '').localeCompare(String(a.release_date || ''));
    if (sortSel === 'total_supply') return (b.total_supply || 0) - (a.total_supply || 0);
    if (sortSel === 'avatars_total') return (b.avatars_total || 0) - (a.avatars_total || 0);
    return String(a.name || '').localeCompare(String(b.name || ''));
  });
  return rows;
}

function filter() {
  const rows = applyCollectionFilters();
  _collRows = rows;
  document.getElementById('collCount').innerHTML = `<b>${rows.length}</b> of ${DATA.collections.length} collections`;
  document.getElementById('emptyState').style.display = rows.length ? 'none' : 'block';
  document.getElementById('collectionsGrid').innerHTML = rows.map((c, i) => collectionCard(c, i)).join('');
}

function isVideoUrl(u) { return !!u && (u.includes('.mp4') || u.includes('stream.mux.com') || u.includes('.m3u8')); }





function vrmReachBadge(c) {
  const s = c.vrm_check_status;
  if (s === 'ok_vrm') {
    const mb = c.vrm_check_bytes ? (c.vrm_check_bytes / 1048576).toFixed(1) + ' MB' : '';
    return `<span class="badge vrm-live" title="One sample VRM was fetched and parsed OK${mb ? ' — that file is ' + mb : ''}. Source: ${esc(c.vrm_check_url || '')}">VRM verified${mb ? ' · ' + mb : ''}</span>`;
  }
  if (s === 'reachable_not_vrm') return '<span class="badge vrm-warn" title="File reachable but not a valid VRM/GLB">Not a VRM</span>';
  if (s === 'no_url') return '<span class="badge vrm-none" title="No VRM URL on record — unknown where the VRM lives">No VRM URL</span>';
  if (c.vrm_reachable === 0) return `<span class="badge vrm-dead" title="Unreachable: ${esc(s || '')}${c.vrm_check_http ? ' ' + c.vrm_check_http : ''}">Unreachable</span>`;
  return '';
}

function collectionCard(c, i) {
  const id = c.id;
  const letter = esc((c.name || '?').trim().charAt(0).toUpperCase() || '?');
  const art = c.image_url || c.sample_nft_image ||
              ((c.banner_image_url && !isVideoUrl(c.banner_image_url)) ? c.banner_image_url : null);
  const thumb = art
    ? `<img loading="lazy" src="${esc(art)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'crow-fallback',textContent:'${letter}'}))">`
    : `<div class="crow-fallback">${letter}</div>`;

  const facts = [];
  if (c.release_date) facts.push(`<span title="Launch date">${esc(String(c.release_date).slice(0, 7))}</span>`);
  if (c.chain) facts.push(esc(c.chain));

  // ONE size number. `supply` is how big the collection is; `files` is how many
  // VRM files we actually hold and checked. They are usually identical, so they
  // are merged — and only split when we genuinely hold a subset.
  const supply = c.total_supply || null;
  const files = c.avatars_total || 0;
  const okFiles = c.avatars_reachable || 0;
  if (supply) facts.push(supplyText(c));
  else if (files) facts.push(`${files.toLocaleString()} files`);
  if (files) {
    const allOk = okFiles === files;
    const cls = allOk ? 'av-all' : 'av-part';
    const subset = supply && files < supply;
    const label = allOk
      ? (subset ? `${files.toLocaleString()} checked · all reachable` : 'all reachable')
      : `${okFiles.toLocaleString()}/${files.toLocaleString()} files reachable`;
    facts.push(`<span class="${cls}" title="Every individual VRM file we hold for this collection was fetched and verified">${label}</span>`);
  }
  if (c.floor_price) facts.push(`floor ${c.floor_price.toFixed(2)} ${esc(c.floor_price_symbol || '')}`);

  const vrmBtn = c.vrm_url_https
    ? `<button class="vrm-btn" data-vrm="${i}">View</button>`
    : `<button class="vrm-btn ghost" disabled>—</button>`;
  const descText = c.curated_description || c.description || '';

  return `<div class="crow">
    <div class="crow-thumb" data-img="${i}">${thumb}</div>
    <div class="crow-main">
      <div class="crow-line1">
        <span class="crow-name">${esc(c.name)}</span>
        ${c.creator ? `<span class="crow-creator">${esc(c.creator)}</span>` : ''}
        ${vrmReachBadge(c)}${licenseBadge(c.license_category, c)}
        ${c.vipe_category ? `<span class="chip vipe-cat">${esc(c.vipe_category)}</span>` : ''}
        ${chainChips(c)}
      </div>
      <div class="crow-line2">
        ${facts.length ? `<span class="crow-facts">${facts.join(' · ')}</span>` : ''}
        ${descText ? `<span class="crow-desc">${esc(descText)}</span>` : ''}
      </div>
    </div>
    <div class="crow-actions">
      ${collLinks(c)}
      ${vrmBtn}
    </div>
  </div>`;
}


// Event delegation: VRM buttons + image previews (no fragile inline handlers).
function wireDelegation() {
  const collView = document.getElementById('collectionsView');
  collView.addEventListener('click', e => {
    const v = e.target.closest('[data-vrm]');
    if (v) { const c = _collRows[+v.dataset.vrm]; if (c && c.vrm_url_https) openVrmViewer(c.vrm_url_https, c.name, c.vrm_url_https); return; }
    const im = e.target.closest('[data-img]');
    if (im) { const c = _collRows[+im.dataset.img]; if (c) { const src = c.image_url || c.sample_nft_image || c.banner_image_url; if (src && !isVideoUrl(src)) showImg(src, c.name, isVideoUrl(c.banner_image_url) ? null : c.banner_image_url); } }
  });
}

// ─── Image preview modal ───────────────────────────────────────────────────
function showImg(url, name, bannerUrl) {
  if (!url) return;
  const img = document.getElementById('imgModalImg');
  const banner = document.getElementById('imgModalBanner');
  const label = document.getElementById('imgModalLabel');
  img.src = url;
  img.alt = name || '';
  const isVideo = bannerUrl && (bannerUrl.includes('.mp4') || bannerUrl.includes('stream.mux.com'));
  if (bannerUrl && !isVideo) { banner.src = bannerUrl; banner.style.display = ''; }
  else { banner.style.display = 'none'; banner.src = ''; }
  label.textContent = name || '';
  document.getElementById('imgModal').classList.add('active');
}
function closeImgModal() {
  document.getElementById('imgModal').classList.remove('active');
  document.getElementById('imgModalImg').src = '';
  document.getElementById('imgModalBanner').src = '';
}

// ─── VRM viewer modal (Three.js + @pixiv/three-vrm via ES modules) ──────────
let vrmAnimId = null;

function showVrmError(msg) {
  document.getElementById('vrmLoading').classList.remove('active');
  const err = document.getElementById('vrmError');
  err.textContent = msg;
  err.classList.add('active');
}
// The viewer ES module runs in its own scope — expose the error hook to it.
window._showVrmError = showVrmError;

function openVrmViewer(vrmUrl, name, footerInfo) {
  if (!vrmUrl) { alert('No VRM URL available for this collection.'); return; }
  document.getElementById('vrmModalTitle').textContent = 'VRM Viewer — ' + (name || '');
  document.getElementById('vrmModal').classList.add('active');
  const loadingEl = document.getElementById('vrmLoading');
  loadingEl.textContent = 'Loading VRM…';
  loadingEl.classList.add('active');
  // The canvas container has zero size until the modal is displayed.
  if (window._vrmResize) requestAnimationFrame(() => window._vrmResize());
  document.getElementById('vrmError').classList.remove('active');
  document.getElementById('vrmFooterInfo').textContent = footerInfo || '';
  document.getElementById('vrmFooterLink').href = vrmUrl;

  if (window._vrmViewerReady) {
    window._initVrmScene(vrmUrl);
  } else {
    const s = document.createElement('script');
    s.type = 'module';
    // three-vrm v3 API, mirroring packages/avatars/lab VRMViewer.tsx:
    //   GLTFLoader.register(VRMLoaderPlugin) -> gltf.userData.vrm
    //   removeUnnecessaryVertices + combineSkeletons (guarded)
    //   rotateVRM0() so VRM 0.x models face the camera
    //   deepDispose(vrm.scene) on teardown
    s.textContent = `
      // Bare specifiers — resolved by the import map in index.html so three and
      // three-vrm share a single three instance.
      import * as THREE from 'three';
      import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
      import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
      import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

      let scene = null, renderer = null, camera = null, controls = null, currentVrm = null, clock = null;

      function disposeCurrent() {
        if (currentVrm) {
          scene.remove(currentVrm.scene);
          VRMUtils.deepDispose(currentVrm.scene);
          currentVrm = null;
        }
      }

      function frameModel(vrm) {
        // Fit by bounding SPHERE + fov so any avatar shape/scale is fully framed
        // with margin (a box-height heuristic put the camera inside wide models).
        const box = new THREE.Box3().setFromObject(vrm.scene);
        const sphere = box.getBoundingSphere(new THREE.Sphere());
        const center = sphere.center;
        const radius = Math.max(sphere.radius, 0.05);
        const vFov = THREE.MathUtils.degToRad(camera.fov);
        const fitV = radius / Math.sin(vFov / 2);
        const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect);
        const fitH = radius / Math.sin(hFov / 2);
        const dist = Math.max(fitV, fitH) * 1.25;  // 25% margin
        camera.position.set(0, center.y, dist);
        camera.near = Math.max(0.01, dist / 500);
        camera.far = dist * 50;
        camera.updateProjectionMatrix();
        controls.target.copy(center);
        controls.target.x = 0;
        controls.update();
      }

      function resize() {
        const c = document.getElementById('vrmCanvasContainer');
        if (!c || !renderer || !camera) return;
        const w = c.clientWidth, h = c.clientHeight;
        if (!w || !h) return;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      }
      window.addEventListener('resize', resize);
      window._vrmResize = resize;

      // Public IPFS gateways 504/429 constantly (a production load failed on
      // ipfs.io). Build an ordered candidate list so one dead gateway is not a
      // dead avatar — mirrors the fallback in scripts/check_vrm_reachable.py.
      function urlCandidates(u) {
        const out = [u];
        const m = /\\/ipfs\\/([A-Za-z0-9]+)(\\/.*)?$/.exec(u);
        if (m) {
          const cid = m[1], path = m[2] || '';
          for (const gw of ['https://ipfs.io', 'https://dweb.link', 'https://cloudflare-ipfs.com', 'https://gateway.pinata.cloud']) {
            const alt = gw + '/ipfs/' + cid + path;
            if (!out.includes(alt)) out.push(alt);
          }
        }
        return out;
      }

      window._initVrmScene = function(vrmUrl) {
        const canvas = document.getElementById('vrmCanvas');
        const container = document.getElementById('vrmCanvasContainer');
        const w = container.clientWidth || 800, h = container.clientHeight || 500;

        if (!scene) {
          scene = new THREE.Scene();
          clock = new THREE.Clock();
          camera = new THREE.PerspectiveCamera(30, w / h, 0.1, 100);
          renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
          renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
          renderer.setSize(w, h, false);
          renderer.outputColorSpace = THREE.SRGBColorSpace;
          scene.add(new THREE.AmbientLight(0xffffff, 2.0));
          const dir = new THREE.DirectionalLight(0xffffff, 1.6);
          dir.position.set(1, 2, 2);
          scene.add(dir);
          const rim = new THREE.DirectionalLight(0x8899ff, 0.7);
          rim.position.set(-2, 1, -2);
          scene.add(rim);
          controls = new OrbitControls(camera, renderer.domElement);
          controls.enableDamping = true;
          controls.dampingFactor = 0.1;
          controls.minDistance = 0.3;
          controls.maxDistance = 40;

          const render = () => {
            requestAnimationFrame(render);
            const dt = clock.getDelta();
            if (currentVrm) currentVrm.update(dt);
            if (controls) controls.update();
            renderer.render(scene, camera);
          };
          render();
        }
        resize();
        disposeCurrent();

        const loader = new GLTFLoader();
        loader.crossOrigin = 'anonymous';
        loader.register((parser) => new VRMLoaderPlugin(parser));

        const candidates = urlCandidates(vrmUrl);
        let attempt = 0;
        const tryLoad = () => loader.load(
          candidates[attempt],
          (gltf) => {
            const vrm = gltf.userData.vrm;
            if (!vrm) {
              window._showVrmError('This file loaded but contains no VRM extension (plain glTF/GLB).');
              return;
            }
            try { VRMUtils.removeUnnecessaryVertices(gltf.scene); } catch (e) {}
            try { VRMUtils.combineSkeletons(gltf.scene); } catch (e) {}
            // VRM 0.x faces -Z; rotate so the avatar faces the camera.
            try { VRMUtils.rotateVRM0(vrm); } catch (e) {}
            vrm.scene.traverse((o) => { o.frustumCulled = false; });

            currentVrm = vrm;
            scene.add(vrm.scene);
            frameModel(vrm);

            // Several VRMs carry the literal string "undefined" in meta fields —
            // treat those as empty rather than printing them.
            const clean = (v) => {
              const s = Array.isArray(v) ? v.filter(Boolean).join(', ') : (v == null ? '' : String(v));
              return (!s || s === 'undefined' || s === 'null') ? '' : s;
            };
            const m = vrm.meta || {};
            const title = clean(m.name) || clean(m.title);
            const author = clean(m.authors) || clean(m.author);
            const spec = (m.metaVersion === '1' || m.licenseUrl) ? 'VRM 1.0' : 'VRM 0.x';
            const bits = [spec];
            if (title) bits.push(title);
            if (author) bits.push('by ' + author);
            const lic = clean(m.licenseName) || clean(m.licenseUrl);
            if (lic) bits.push(lic);
            document.getElementById('vrmFooterInfo').textContent = bits.join(' · ');
            document.getElementById('vrmLoading').classList.remove('active');
          },
          (prog) => {
            if (prog && prog.total) {
              const pct = Math.round((prog.loaded / prog.total) * 100);
              const el = document.getElementById('vrmLoading');
              if (el) el.textContent = 'Loading VRM… ' + pct + '%';
            } else if (prog && prog.loaded) {
              const el = document.getElementById('vrmLoading');
              if (el) el.textContent = 'Loading VRM… ' + Math.round(prog.loaded / 1024) + ' KB';
            }
          },
          (err) => {
            attempt++;
            if (attempt < candidates.length) {
              const el = document.getElementById('vrmLoading');
              if (el) el.textContent = 'Gateway failed — trying mirror ' + attempt + '…';
              tryLoad();
              return;
            }
            window._showVrmError('Could not load this VRM: ' + ((err && err.message) || 'network or CORS error') +
              (candidates.length > 1 ? ' (tried ' + candidates.length + ' gateways)' : '') +
              '. The host may block cross-origin requests — use the direct link below.');
          }
        );
        tryLoad();
      };

      window._vrmDispose = disposeCurrent;
      // Debug hook: deterministic proof of what is actually in the scene.
      window._vrmState = function() {
        if (!currentVrm) return { loaded: false };
        const box = new THREE.Box3().setFromObject(currentVrm.scene);
        const size = box.getSize(new THREE.Vector3());
        let meshes = 0, visible = 0;
        currentVrm.scene.traverse((o) => { if (o.isMesh || o.isSkinnedMesh) { meshes++; if (o.visible) visible++; } });
        return {
          loaded: true, meshes, visible,
          height: +size.y.toFixed(2), width: +size.x.toFixed(2),
          camY: +camera.position.y.toFixed(2), camZ: +camera.position.z.toFixed(2),
          targetY: +controls.target.y.toFixed(2),
          inFrustum: (function () {
            camera.updateMatrixWorld();
            const m = new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
            return new THREE.Frustum().setFromProjectionMatrix(m).intersectsBox(box);
          })(),
          canvas: renderer.domElement.width + 'x' + renderer.domElement.height,
        };
      };
      window._vrmViewerReady = true;
      if (window._pendingVrmUrl) {
        const url = window._pendingVrmUrl;
        window._pendingVrmUrl = null;
        window._initVrmScene(url);
      }
    `;
    document.head.appendChild(s);
    window._pendingVrmUrl = vrmUrl;
  }
}

function closeVrmModal() {
  document.getElementById('vrmModal').classList.remove('active');
  if (vrmAnimId) { cancelAnimationFrame(vrmAnimId); vrmAnimId = null; }
  // Free GPU memory: official deepDispose + drop the ref (lab lifecycle contract).
  if (window._vrmDispose) window._vrmDispose();
  document.getElementById('vrmError').classList.remove('active');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeVrmModal(); closeImgModal(); }
});

// ─── Init ────────────────────────────────────────────────────────────────────
wireDelegation();
(async () => {
  try {
    await loadBuildInfo();
    await loadCollections();
  } catch (err) {
    document.getElementById('collectionsGrid').innerHTML =
      `<div class="loading-msg">Failed to load catalog data: ${esc(err.message)}<br>Run <code>python scripts/build_catalog.py</code> to generate data files.</div>`;
    console.error(err);
  }
})();

// ─── Service worker registration (offline cache for hashed static files) ────
if ('serviceWorker' in navigator) {
  const swScope = location.protocol === 'https:' || location.hostname === 'localhost' ? './sw.js' : null;
  if (swScope) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register(swScope).catch((err) => {
        console.warn('sw registration failed:', err);
      });
    });
  }
}
