// ─── Data loading (lazy, content-hashed JSON files) ──────────────────────────
let DATA = { collections: [], opensea: [], avatars: [] };
let BUILD_INFO = null;
let _openseaLoaded = false;
let _openseaLoading = false;
let _avatarsLoaded = false;
let _avatarsLoading = false;

async function fetchJSON(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`Failed to load ${path}: ${resp.status}`);
  return resp.json();
}

async function loadBuildInfo() {
  BUILD_INFO = await fetchJSON('data/build-info.json');
  return BUILD_INFO;
}

function setStat(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

async function loadCollections() {
  const info = BUILD_INFO || await loadBuildInfo();
  const [summary, collectionsData] = await Promise.all([
    fetchJSON('data/' + info.files.summary),
    fetchJSON('data/' + info.files.collections),
  ]);
  DATA.collections = collectionsData.collections || [];
  const s = summary.stats || {};
  setStat('stat-collections', s.collections ?? DATA.collections.length);
  setStat('stat-avatars', (s.avatars ?? 0).toLocaleString());
  setStat('stat-os', s.os ?? 0);
  setStat('stat-green', s.green ?? 0);
  setStat('stat-yellow', s.yellow ?? 0);
  setStat('stat-red', s.red ?? 0);
  setStat('stat-alive', s.alive ?? 0);
  setStat('stat-dead', s.dead ?? 0);
  setStat('stat-wayback', s.wayback ?? 0);
  setStat('stat-dc-alive', s.dc_alive ?? 0);
  setStat('stat-dc-dead', s.dc_dead ?? 0);
  setStat('stat-capped', s.capped ?? 0);
  setStat('stat-ongoing', s.ongoing ?? 0);
  checkStaleStats();
  filter();
}

function checkStaleStats() {
  const asOf = BUILD_INFO && BUILD_INFO.market_data_as_of;
  if (!asOf) return;
  const ageMs = Date.now() - new Date(asOf).getTime();
  const STALE_THRESHOLD_MS = 48 * 60 * 60 * 1000;  // 48 hours
  const el = document.getElementById('stat-stale');
  if (!el) return;
  if (ageMs > STALE_THRESHOLD_MS) {
    const hours = Math.floor(ageMs / (60 * 60 * 1000));
    el.textContent = `⚠ market data ${hours}h old`;
    el.style.display = '';
  } else {
    el.style.display = 'none';
  }
}

async function loadOpensea() {
  if (_openseaLoaded || _openseaLoading) return;
  _openseaLoading = true;
  const info = BUILD_INFO || await loadBuildInfo();
  const data = await fetchJSON('data/' + info.files.opensea);
  DATA.opensea = data.candidates || [];
  _openseaLoaded = true;
  _openseaLoading = false;
  filterOS();
}

async function loadAvatars() {
  if (_avatarsLoaded || _avatarsLoading) return;
  _avatarsLoading = true;
  const info = BUILD_INFO || await loadBuildInfo();
  const shards = info.files.avatars || [];
  const results = await Promise.all(shards.map(s => fetchJSON('data/' + s)));
  DATA.avatars = results.flatMap(r => r.avatars || []);
  _avatarsLoaded = true;
  _avatarsLoading = false;
  filterAvatars();
}

// ─── Shared helpers ─────────────────────────────────────────────────────────
let sortKey = 'name', sortAsc = true, sortKeyOS = 'slug', sortAscOS = true;
let currentTab = 'collections';
let collectionsViewMode = 'cards';
let _collRows = [];
let _osRows = [];

function esc(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : ''; }
function badge(cls, text) { return `<span class="badge badge-${cls}">${esc(text)}</span>`; }

function licenseBadge(cat, c) {
  const map = { green: '🟢 CC0', yellow: '🟡 Holder', red: '🔴 Restricted', unknown: '? Unknown' };
  const label = map[cat] || '? Unknown';
  if (!c) return badge(cat || 'unknown', label);
  const rc = c.reason_codes || [];
  const conf = c.license_confidence || 'unknown';
  const parts = [label];
  if (rc.length) parts.push(rc.join(', '));
  parts.push(`[${conf}]`);
  return `<span class="badge badge-${cat || 'unknown'}" title="${esc(parts.join(' — '))}">${esc(label)}</span>`;
}

function tierBadge(tier) {
  const map = { A: 'Tier A', B: 'Tier B', C: 'Tier C', arweave: 'Arweave', infra: 'Infra', not_vrm: 'Not VRM' };
  return badge(`tier-${tier || 'unknown'}`, map[tier] || tier || '?');
}

function supplyText(c) {
  if (!c.total_supply) return null;
  const ms = c.mint_status;
  let icon = '❓';
  if (ms === 'capped' || ms === 'likely_capped') icon = '🔒';
  else if (ms === 'ongoing') icon = '🟢';
  return `${icon} ${c.total_supply.toLocaleString()}`;
}

function collLinks(c) {
  const out = [];
  if (c.opensea_slug) out.push(`<a class="icon-link" href="https://opensea.io/collection/${encodeURIComponent(c.opensea_slug)}" target="_blank" rel="noopener" title="OpenSea">⛵</a>`);
  if (c.project_url) out.push(`<a class="icon-link" href="${esc(c.project_url)}" target="_blank" rel="noopener" title="Website">🌐</a>`);
  if (c.twitter_username) out.push(`<a class="icon-link" href="https://twitter.com/${esc(c.twitter_username)}" target="_blank" rel="noopener" title="@${esc(c.twitter_username)}">𝕏</a>`);
  if (c.discord_url && c.discord_status === 'alive') out.push(`<a class="icon-link" href="${esc(c.discord_url)}" target="_blank" rel="noopener" title="Discord">💬</a>`);
  const ct = c.contract || ((c.contracts || [])[0] || {}).address;
  if (ct) out.push(`<a class="icon-link mono" href="https://etherscan.io/address/${esc(ct)}" target="_blank" rel="noopener" title="${esc(ct)}">⧉</a>`);
  return out.join('');
}

// ─── Filtering + collection rendering ────────────────────────────────────────
let _filterTimer = null;
function onSearch() {
  clearTimeout(_filterTimer);
  _filterTimer = setTimeout(() => {
    if (currentTab === 'collections') filter();
    else if (currentTab === 'avatars') filterAvatars();
    else filterOS();
  }, 150);
}
function debounceFilter() { onSearch(); }

function setCollectionsView(mode) {
  collectionsViewMode = mode;
  document.getElementById('vm-cards').classList.toggle('active', mode === 'cards');
  document.getElementById('vm-table').classList.toggle('active', mode === 'table');
  document.getElementById('collectionsGrid').style.display = mode === 'cards' ? '' : 'none';
  document.getElementById('collectionsTableWrap').style.display = mode === 'table' ? '' : 'none';
  filter();
}

function applyCollectionFilters() {
  const q = document.getElementById('search').value.toLowerCase();
  const fTier = document.getElementById('f-tier').value;
  const fChain = document.getElementById('f-chain').value;
  const fLicense = document.getElementById('f-license').value;
  const fMint = document.getElementById('f-mint').value;
  let rows = DATA.collections.filter(c => {
    if (fTier && c.tier !== fTier) return false;
    if (fChain && c.chain !== fChain) return false;
    if (fLicense && (c.license_category || 'unknown') !== fLicense) return false;
    if (fMint && (c.mint_status || '') !== fMint) return false;
    if (q) {
      const hay = [c.name, c.contract, c.opensea_slug, c.vrm_license, c.creator, c.notes, c.description].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  rows.sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (typeof va === 'number' || typeof vb === 'number') return sortAsc ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
    return sortAsc ? String(va || '').localeCompare(String(vb || '')) : String(vb || '').localeCompare(String(va || ''));
  });
  return rows;
}

function filter() {
  if (currentTab !== 'collections') return;
  const rows = applyCollectionFilters();
  _collRows = rows;
  document.getElementById('collCount').innerHTML = `<b>${rows.length}</b> of ${DATA.collections.length} collections`;
  document.getElementById('emptyState').style.display = rows.length ? 'none' : 'block';
  if (collectionsViewMode === 'cards') {
    document.getElementById('collectionsGrid').innerHTML = rows.map((c, i) => collectionCard(c, i)).join('');
  } else {
    renderCollectionTable(rows);
  }
}

function collectionCard(c, i) {
  const letter = esc((c.name || '?').trim().charAt(0).toUpperCase() || '?');
  const banner = c.banner_image_url
    ? `<img loading="lazy" src="${esc(c.banner_image_url)}" alt="" onerror="this.style.display='none'">`
    : `<div class="fallback">${letter}</div>`;
  const pfpSrc = c.image_url || c.sample_nft_image;
  const pfp = pfpSrc
    ? `<img class="ccard-pfp" loading="lazy" src="${esc(pfpSrc)}" alt="" onerror="this.outerHTML='<div class=&quot;ccard-pfp fallback-pfp&quot;>🖼</div>'">`
    : `<div class="ccard-pfp fallback-pfp">🖼</div>`;
  const chips = [];
  if (c.chain) chips.push(`<span class="chip"><span class="k">⛓</span> ${esc(c.chain)}</span>`);
  const sup = supplyText(c); if (sup) chips.push(`<span class="chip">${sup}</span>`);
  if (c.floor_price) chips.push(`<span class="chip"><span class="k">floor</span> <b>${c.floor_price.toFixed(2)} ${esc(c.floor_price_symbol || '')}</b></span>`);
  if (c.avatar_count) chips.push(`<span class="chip"><span class="k">avatars</span> <b>${c.avatar_count.toLocaleString()}</b></span>`);
  const vrmBtn = c.vrm_url_https
    ? `<button class="vrm-btn" data-vrm="${i}">▶ View VRM</button>`
    : `<button class="vrm-btn ghost" disabled>No VRM</button>`;
  const vrmLic = c.vrm_license ? ` <span class="badge badge-unknown">${esc(c.vrm_license)}</span>` : '';
  return `<div class="ccard">
    <div class="ccard-banner" data-img="${i}">
      ${banner}
      <div class="ccard-tier">${tierBadge(c.tier)}</div>
      ${pfp}
    </div>
    <div class="ccard-body">
      <div class="ccard-title">
        <span class="ccard-name">${esc(c.name)}</span>
        ${c.creator ? `<span class="ccard-creator">by ${esc(c.creator)}</span>` : ''}
      </div>
      <div class="ccard-badges">${licenseBadge(c.license_category, c)}${vrmLic}</div>
      ${chips.length ? `<div class="ccard-chips">${chips.join('')}</div>` : ''}
      <div class="ccard-foot">${vrmBtn}<div class="ccard-links">${collLinks(c)}</div></div>
    </div>
  </div>`;
}

function renderCollectionTable(rows) {
  document.getElementById('collectionsBody').innerHTML = rows.map((c, i) => {
    const src = c.image_url || c.sample_nft_image;
    const img = src
      ? `<img class="thumb" loading="lazy" src="${esc(src)}" alt="" data-img="${i}" onerror="this.outerHTML='<span class=&quot;thumb-placeholder&quot;>🖼</span>'">`
      : '<span class="thumb-placeholder">🖼</span>';
    const sup = supplyText(c) || '—';
    const vrmBtn = c.vrm_url_https ? `<button class="vrm-btn" data-vrm="${i}">▶</button>` : '—';
    return `<tr>
      <td>${img}</td>
      <td><b style="color:var(--text-primary)">${esc(c.name)}</b>${c.creator ? `<br><span class="mono">${esc(c.creator)}</span>` : ''}</td>
      <td>${tierBadge(c.tier)}</td>
      <td>${esc(c.chain || '—')}</td>
      <td>${licenseBadge(c.license_category, c)}</td>
      <td class="mono">${esc(c.vrm_license || '—')}</td>
      <td>${sup}</td>
      <td class="mono">${c.floor_price ? c.floor_price.toFixed(2) + ' ' + esc(c.floor_price_symbol || '') : '—'}</td>
      <td class="mono">${c.avatar_count ? c.avatar_count.toLocaleString() : '—'}</td>
      <td>${collLinks(c)}</td>
      <td>${vrmBtn}</td>
    </tr>`;
  }).join('');
}

// ─── Avatars view ────────────────────────────────────────────────────────────
function filterAvatars() {
  if (!_avatarsLoaded) {
    document.getElementById('avatarGrid').innerHTML = '<div class="loading-msg">Loading avatars…</div>';
    loadAvatars();
    return;
  }
  const q = (document.getElementById('search').value || '').toLowerCase();
  let rows = DATA.avatars.filter(a => {
    if (!q) return true;
    const hay = [a.name, a.collection_id, a.description, a.model_file_url].join(' ').toLowerCase();
    return hay.includes(q);
  });
  const shown = rows.slice(0, 600);
  document.getElementById('avatarCount').innerHTML =
    `<b>${shown.length}</b> of ${DATA.avatars.length} avatars${rows.length > shown.length ? ' (showing first 600)' : ''}`;
  document.getElementById('avatarGrid').innerHTML = shown.map(a => `<div class="avatar-card">
    <div class="thumb-box">${a.thumbnail_url ? `<img loading="lazy" src="${esc(a.thumbnail_url)}" alt="" onerror="this.parentNode.textContent='🖼'">` : '🖼'}</div>
    <h4>${esc(a.name || '—')}</h4>
    <div class="mono">${esc(a.collection_id || '')}</div>
    ${a.model_file_url ? `<a href="${esc(a.model_file_url)}" target="_blank" rel="noopener">Download VRM ↓</a>` : ''}
  </div>`).join('');
}

// ─── OpenSea candidates view ─────────────────────────────────────────────────
function filterOS() {
  if (!_openseaLoaded) {
    document.getElementById('osBody').innerHTML = '<tr><td colspan="9" class="loading-msg">Loading OpenSea candidates…</td></tr>';
    loadOpensea();
    return;
  }
  const q = document.getElementById('search').value.toLowerCase();
  let rows = DATA.opensea.filter(c => {
    if (q) { const hay = [c.slug, c.name, c.contract, c.vrm_url].join(' ').toLowerCase(); if (!hay.includes(q)) return false; }
    return true;
  });
  rows.sort((a, b) => {
    let va = a[sortKeyOS] || '', vb = b[sortKeyOS] || '';
    return sortAscOS ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
  });
  _osRows = rows;
  document.getElementById('osBody').innerHTML = rows.map((c, i) => {
    const osImg = c.image_url
      ? `<img class="thumb" loading="lazy" src="${esc(c.image_url)}" alt="" data-osimg="${i}" onerror="this.outerHTML='<span class=&quot;thumb-placeholder&quot;>🖼</span>'">`
      : '<span class="thumb-placeholder">🖼</span>';
    const osVrmBtn = c.vrm_url_https ? `<button class="vrm-btn" data-vrm="${i}">▶ VRM</button>` : '—';
    return `<tr>
      <td>${osImg}</td>
      <td>${c.slug ? `<a href="https://opensea.io/collection/${encodeURIComponent(c.slug)}" target="_blank" rel="noopener">${esc(c.slug)}</a>` : '—'}</td>
      <td>${esc(c.name || '—')}</td>
      <td>${esc(c.chain || '—')}</td>
      <td>${badge(c.status === 'vrm' ? 'green' : c.status === 'no_vrm' ? 'unknown' : 'yellow', c.status || '?')}</td>
      <td class="mono">${esc(c.vrm_param || '—')}</td>
      <td>${osVrmBtn}</td>
      <td class="mono">${c.contract ? `<a href="https://etherscan.io/address/${esc(c.contract)}" target="_blank" rel="noopener">${c.contract.slice(0, 8)}…</a>` : '—'}</td>
      <td class="mono">${esc(c.source_query || '—')}</td>
    </tr>`;
  }).join('');
}

function sort(key) { if (sortKey === key) sortAsc = !sortAsc; else { sortKey = key; sortAsc = true; } filter(); }
function sortOS(key) { if (sortKeyOS === key) sortAscOS = !sortAscOS; else { sortKeyOS = key; sortAscOS = true; } filterOS(); }

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('#viewSwitch .seg').forEach(b => b.classList.toggle('active', b.dataset.view === tab));
  document.getElementById('collectionsView').style.display = tab === 'collections' ? '' : 'none';
  document.getElementById('avatarsView').style.display = tab === 'avatars' ? '' : 'none';
  document.getElementById('openseaView').style.display = tab === 'opensea' ? '' : 'none';
  if (tab === 'collections') filter();
  else if (tab === 'avatars') filterAvatars();
  else filterOS();
}

// Event delegation: VRM buttons + image previews (no fragile inline handlers).
function wireDelegation() {
  document.getElementById('collectionsView').addEventListener('click', e => {
    const v = e.target.closest('[data-vrm]');
    if (v) { const c = _collRows[+v.dataset.vrm]; if (c && c.vrm_url_https) openVrmViewer(c.vrm_url_https, c.name, c.vrm_url_https); return; }
    const im = e.target.closest('[data-img]');
    if (im) { const c = _collRows[+im.dataset.img]; if (c) { const src = c.image_url || c.sample_nft_image || c.banner_image_url; if (src) showImg(src, c.name, c.banner_image_url); } }
  });
  document.getElementById('openseaView').addEventListener('click', e => {
    const v = e.target.closest('[data-vrm]');
    if (v) { const c = _osRows[+v.dataset.vrm]; if (c && c.vrm_url_https) openVrmViewer(c.vrm_url_https, c.name, c.vrm_url_https); return; }
    const im = e.target.closest('[data-osimg]');
    if (im) { const c = _osRows[+im.dataset.osimg]; if (c && c.image_url) showImg(c.image_url, c.name, c.banner_image_url); }
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

function openVrmViewer(vrmUrl, name, footerInfo) {
  if (!vrmUrl) { alert('No VRM URL available for this collection.'); return; }
  document.getElementById('vrmModalTitle').textContent = 'VRM Viewer — ' + (name || '');
  document.getElementById('vrmModal').classList.add('active');
  document.getElementById('vrmLoading').classList.add('active');
  document.getElementById('vrmError').classList.remove('active');
  document.getElementById('vrmFooterInfo').textContent = footerInfo || '';
  document.getElementById('vrmFooterLink').href = vrmUrl;

  if (window._vrmViewerReady) {
    window._initVrmScene(vrmUrl);
  } else {
    const s = document.createElement('script');
    s.type = 'module';
    s.textContent = `
      import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
      import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/GLTFLoader.js';
      import { VRM, VRMUtils } from 'https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.3.2/+esm';

      let scene = null, renderer = null, camera = null, model = null;

      window._initVrmScene = function(vrmUrl) {
        const canvas = document.getElementById('vrmCanvas');
        const container = document.getElementById('vrmCanvasContainer');
        const w = container.clientWidth, h = container.clientHeight;

        if (!scene) {
          scene = new THREE.Scene();
          scene.background = new THREE.Color(0x0D0D0F);
          camera = new THREE.PerspectiveCamera(30, w / h, 0.1, 100);
          camera.position.set(0, 1.3, 4);
          camera.lookAt(0, 1.3, 0);
          renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
          renderer.setPixelRatio(window.devicePixelRatio);
          renderer.setSize(w, h);
          const amb = new THREE.AmbientLight(0xffffff, 0.9);
          scene.add(amb);
          const dir = new THREE.DirectionalLight(0xffffff, 0.5);
          dir.position.set(1, 2, 1);
          scene.add(dir);

          let theta = 0, phi = 0.1, isDragging = false, lastX = 0, lastY = 0;
          canvas.addEventListener('mousedown', e => { isDragging = true; lastX = e.clientX; lastY = e.clientY; });
          window.addEventListener('mouseup', () => { isDragging = false; });
          window.addEventListener('mousemove', e => {
            if (!isDragging) return;
            theta -= (e.clientX - lastX) * 0.01;
            phi = Math.max(-0.5, Math.min(0.8, phi + (e.clientY - lastY) * 0.01));
            lastX = e.clientX; lastY = e.clientY;
            const r = camera.position.length();
            camera.position.set(r * Math.sin(theta) * Math.cos(phi), 1.3 + r * Math.sin(phi), r * Math.cos(theta) * Math.cos(phi));
            camera.lookAt(0, 1.3, 0);
          });
          canvas.addEventListener('wheel', e => {
            e.preventDefault();
            const r = Math.max(1.5, Math.min(10, camera.position.length() + e.deltaY * 0.005));
            camera.position.setLength(r);
          });
        } else if (model) {
          scene.remove(model);
          VRMUtils.deepDispose(model);
          model = null;
        }

        const loader = new GLTFLoader();
        loader.load(vrmUrl, (gltf) => {
          VRM.from(gltf.scene).then((vrm) => {
            model = gltf.scene;
            scene.add(model);
            VRMUtils.removeUnnecessaryVertices(gltf.scene);

            vrm.humanoid?.resetNormalizedPose();
            if (vrm.humanoid) { vrm.humanoid.setNormalizedPose(); }

            const meta = vrm.meta;
            if (meta) {
              const metaName = meta.name || meta.title || 'Unknown';
              document.getElementById('vrmFooterInfo').textContent =
                'VRM: ' + metaName + ' | Author: ' + (meta.authors || meta.author || '?');
            }

            document.getElementById('vrmLoading').classList.remove('active');

            if (vrmAnimId) cancelAnimationFrame(vrmAnimId);
            const clock = new THREE.Clock();
            function animate() {
              vrmAnimId = requestAnimationFrame(animate);
              const delta = clock.getDelta();
              if (model) vrm.update(delta);
              renderer.render(scene, camera);
            }
            animate();
          }).catch(err => {
            showVrmError('Failed to parse VRM: ' + err.message);
          });
        }, undefined, (err) => {
          showVrmError('Failed to load VRM file. The IPFS gateway may be slow or the file may be unavailable. Try the direct link below.');
        });
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
