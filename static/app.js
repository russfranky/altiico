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

async function loadCollections() {
  const info = BUILD_INFO || await loadBuildInfo();
  const [summary, collectionsData] = await Promise.all([
    fetchJSON('data/' + info.files.summary),
    fetchJSON('data/' + info.files.collections),
  ]);
  DATA.collections = collectionsData.collections || [];
  // Populate header stats from summary
  const s = summary.stats || {};
  document.getElementById('stat-collections').textContent = s.collections ?? DATA.collections.length;
  document.getElementById('stat-avatars').textContent = s.avatars ?? 0;
  document.getElementById('stat-os').textContent = s.os ?? 0;
  document.getElementById('stat-green').textContent = s.green ?? 0;
  document.getElementById('stat-yellow').textContent = s.yellow ?? 0;
  document.getElementById('stat-red').textContent = s.red ?? 0;
  document.getElementById('stat-alive').textContent = s.alive ?? 0;
  document.getElementById('stat-dead').textContent = s.dead ?? 0;
  document.getElementById('stat-wayback').textContent = s.wayback ?? 0;
  document.getElementById('stat-dc-alive').textContent = s.dc_alive ?? 0;
  document.getElementById('stat-dc-dead').textContent = s.dc_dead ?? 0;
  document.getElementById('stat-capped').textContent = s.capped ?? 0;
  document.getElementById('stat-ongoing').textContent = s.ongoing ?? 0;
  checkStaleStats();
  filter();
}

function checkStaleStats() {
  // Warn if market_data_as_of is older than 48 hours (stale_warning_threshold
  // from config/cache_policy.yaml). The warning is shown in the header stats.
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

// ─── App logic (filter, sort, render, modals) ────────────────────────────────
let sortKey = 'name', sortAsc = true, sortKeyOS = 'slug', sortAscOS = true;
let currentTab = 'collections';

function esc(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : ''; }

function badge(cls, text) { return `<span class="badge badge-${cls}">${esc(text)}</span>`; }

function licenseBadge(cat, c) {
  const map = { green: '🟢 CC0', yellow: '🟡 Holder', red: '🔴 Restricted', unknown: '?' };
  const label = map[cat] || '?';
  if (!c) return badge(cat || 'unknown', label);
  // Build tooltip with reason codes and confidence
  const rc = c.reason_codes || [];
  const conf = c.license_confidence || 'unknown';
  const confLabel = { embedded: 'embedded', collection: 'collection', manual: 'manual', unknown: 'unknown', legacy: 'legacy' }[conf] || conf;
  const parts = [label];
  if (rc.length) parts.push(rc.join(', '));
  parts.push(`[${confLabel}]`);
  const title = parts.join(' — ');
  return `<span class="badge badge-${cat || 'unknown'}" title="${esc(title)}">${esc(label)}</span>`;
}

function tierBadge(tier) {
  const map = { A: 'A', B: 'B', C: 'C', arweave: 'Arweave', infra: 'Infra', not_vrm: 'Not VRM' };
  return badge(`tier-${tier || 'unknown'}`, map[tier] || tier || '?');
}

let _filterTimer = null;
function debounceFilter() { clearTimeout(_filterTimer); _filterTimer = setTimeout(filter, 150); }

function filter() {
  if (currentTab !== 'collections') return;
  const q = document.getElementById('search').value.toLowerCase();
  const fTier = document.getElementById('f-tier').value;
  const fChain = document.getElementById('f-chain').value;
  const fLicense = document.getElementById('f-license').value;
  const fUrl = document.getElementById('f-url').value;
  const fDiscord = document.getElementById('f-discord').value;
  const fMint = document.getElementById('f-mint').value;
  let rows = DATA.collections.filter(c => {
    if (fTier && c.tier !== fTier) return false;
    if (fChain && c.chain !== fChain) return false;
    if (fLicense && (c.license_category || 'unknown') !== fLicense) return false;
    if (fUrl === 'wayback') { if (!c.wayback_available) return false; }
    else if (fUrl && (c.url_status || '') !== fUrl) return false;
    if (fDiscord === 'none') { if (c.discord_url) return false; }
    else if (fDiscord && (c.discord_status || '') !== fDiscord) return false;
    if (fMint === 'capped') { if (c.mint_status !== 'capped') return false; }
    else if (fMint === 'likely_capped') { if (c.mint_status !== 'likely_capped') return false; }
    else if (fMint === 'ongoing') { if (c.mint_status !== 'ongoing') return false; }
    else if (fMint === 'no_max_supply') { if (c.mint_status !== 'no_max_supply') return false; }
    const fNftType = document.getElementById('f-nfttype').value;
    if (fNftType && (c.nft_type || 'unknown') !== fNftType) return false;
    if (q) {
      const hay = [c.name, c.contract, c.opensea_slug, c.vrm_license, c.creator, c.notes, c.description]
        .join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  rows.sort((a, b) => {
    let va = a[sortKey] || '', vb = b[sortKey] || '';
    if (typeof va === 'number') return sortAsc ? va - vb : vb - va;
    return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
  });
  const tbody = document.getElementById('collectionsBody');
  tbody.innerHTML = rows.map(c => {
    const us = c.url_status;
    const urlIcon = us === 'alive' ? '✓' : us === 'dead' ? '✗' : us === 'error' ? '?' : '—';
    const urlColor = us === 'alive' ? '#56d364' : us === 'dead' ? '#f85149' : '#8b949e';
    const wbLink = c.wayback_available ? ` <a href="https://web.archive.org/web/*/opensea.io/collection/${c.opensea_slug}" target="_blank" title="${c.wayback_snapshots} snapshots">📦</a>` : '';
    const contracts = (c.contracts || []).map(ct => {
      const explorer = ct.chain === 'polygon' ? 'polygonscan' : ct.chain === 'base' ? 'basescan' : ct.chain === 'optimism' ? 'optimistic.etherscan' : 'etherscan';
      return `<a href="https://${explorer}.io/address/${ct.address}" target="_blank" class="mono" title="${ct.chain}">${ct.address.slice(0,6)}..${ct.address.slice(-4)}</a>`;
    }).join(' ');
    const ds = c.discord_status;
    let dIcon = '—', dColor = '#8b949e', dTitle = '';
    if (ds === 'alive') { dIcon = '✓'; dColor = '#56d364'; dTitle = `${c.discord_members||0} members`; }
    else if (ds === 'dead') { dIcon = '✗'; dColor = '#f85149'; dTitle = 'invite expired/revoked'; }
    else if (ds === 'rate_limited') { dIcon = '⏳'; dColor = '#d29922'; dTitle = 'rate limited'; }
    else if (ds === 'error') { dIcon = '?'; dColor = '#8b949e'; }
    const dLink = c.discord_url && ds === 'alive' ? `<a href="${c.discord_url}" target="_blank" style="color:${dColor}" title="${dTitle}">${dIcon}</a>` : `<span style="color:${dColor}" title="${dTitle}">${dIcon}</span>`;
    const tw = c.twitter_username ? ` <a href="https://twitter.com/${c.twitter_username}" target="_blank" title="@${c.twitter_username}">𝕏</a>` : '';
    const img = c.image_url ? `<img class="thumb" loading="lazy" src="${c.image_url}" alt="${esc(c.name)}" onclick="showImg('${c.image_url}','${esc(c.name)}','${c.banner_image_url || ''}')" onerror="this.outerHTML='<span class=\'thumb-placeholder\'>🖼</span>'">` : '<span class="thumb-placeholder">🖼</span>';
    const vrmBtn = c.vrm_url_https ? `<button class="vrm-btn" onclick="openVrmViewer('${c.vrm_url_https}','${esc(c.name)}','${esc(c.vrm_url_https)}')" title="View VRM in 3D">▶ VRM</button>` : (c.vrm_url_pattern ? '📋' : '—');
    // Supply/mint status
    const ms = c.mint_status;
    let supplyCell = '—';
    if (c.total_supply) {
      let icon = '❓', color = 'var(--text-muted)', title = '';
      if (ms === 'capped') { icon = '🔒'; color = 'var(--success)'; title = 'Mint complete'; }
      else if (ms === 'likely_capped') { icon = '🔒'; color = 'var(--text-muted)'; title = 'Likely capped (>1yr old)'; }
      else if (ms === 'ongoing') { icon = '🟢'; color = 'var(--warning)'; title = `Ongoing: ${c.mint_progress||0}% minted`; }
      else if (ms === 'no_max_supply') { icon = '❓'; color = 'var(--text-muted)'; title = 'No max supply found'; }
      const maxStr = c.max_supply ? `<span class="mono" style="color:var(--text-muted)">/${c.max_supply}</span>` : '';
      const progStr = ms === 'ongoing' ? ` <span style="color:var(--warning);font-size:11px">(${c.mint_progress||0}%)</span>` : '';
      supplyCell = `<span style="color:${color}" title="${title}">${icon}</span> <b style="color:var(--text-primary)">${c.total_supply.toLocaleString()}</b>${maxStr}${progStr}`;
    }
    // NFT type
    const nftIcons = {generative:'🎲', '1of1_series':'🎨', '1of1_art':'🖼', numbered:'🔢', no_traits:'∅', mixed:'🔀', unknown:'❓'};
    const nftLabels = {generative:'Generative', '1of1_series':'1/1 Series', '1of1_art':'1/1 Art', numbered:'Numbered', no_traits:'No Traits', mixed:'Mixed', unknown:'?'};
    const nt = c.nft_type || 'unknown';
    const nftTitle = nftLabels[nt] + (c.avg_traits ? ` — ${c.avg_traits} avg traits, ${c.trait_types_count||0} types` : '');
    const nftCell = `<span title="${nftTitle}">${nftIcons[nt]||'❓'}</span>`;
    return `<tr>
    <td>${img}</td>
    <td><b>${esc(c.name)}</b>${c.creator ? `<br><span class="mono">${esc(c.creator)}</span>` : ''}</td>
    <td>${tierBadge(c.tier)}</td>
    <td class="mono">${esc(c.release_date || '?')}</td>
    <td>${esc(c.chain || '?')}${(c.contracts||[]).length > 1 ? ` <span class="count">(${(c.contracts||[]).length})</span>` : ''}</td>
    <td>${licenseBadge(c.license_category, c)}</td>
    <td>${esc(c.vrm_license || '?')}</td>
    <td>${contracts || (c.contract ? `<a href="https://etherscan.io/address/${c.contract}" target="_blank" class="mono">${c.contract.slice(0,6)}..${c.contract.slice(-4)}</a>` : '—')}</td>
    <td>${c.opensea_slug ? `<a href="https://opensea.io/collection/${c.opensea_slug}" target="_blank">${esc(c.opensea_slug)}</a>` : (c.project_url ? `<a href="${c.project_url}" target="_blank">🌐</a>` : '—')}</td>
    <td style="color:${urlColor}">${urlIcon}${wbLink}</td>
    <td>${dLink}${tw}</td>
    <td>${supplyCell}</td>
    <td class="mono">${c.num_owners ? c.num_owners.toLocaleString() : '—'}</td>
    <td class="mono">${c.floor_price ? `${c.floor_price.toFixed(3)} ${esc(c.floor_price_symbol || '')}` : '—'}</td>
    <td class="mono">${c.total_volume ? c.total_volume.toLocaleString(undefined, {maximumFractionDigits:0}) : '—'}</td>
    <td>${esc(c.category || '—')}</td>
    <td>${c.safelist_status === 'verified' ? '<span style="color:var(--success)">✓</span>' : c.safelist_status === 'approved' ? '<span style="color:var(--warning)">~</span>' : '—'}</td>
    <td>${nftCell}</td>
    <td>${c.avatar_count || '—'}</td>
    <td>${vrmBtn}</td>
    <td class="url-cell mono" title="${esc(c.vrm_url_pattern)}">${esc(c.vrm_url_pattern || '—')}</td>
  </tr>
    ${c.description ? `<tr class="desc-row"><td colspan="20" class="desc-cell">${esc(c.description.slice(0,200))}${c.description.length > 200 ? '…' : ''}</td></tr>` : ''}`}).join('');
  document.getElementById('emptyState').style.display = rows.length ? 'none' : 'block';
  document.getElementById('collectionsTable').style.display = rows.length ? '' : 'none';
}

function filterAvatars() {
  if (!_avatarsLoaded) {
    document.getElementById('avatarGrid').innerHTML = '<div class="loading-msg">Loading avatars...</div>';
    loadAvatars();
    return;
  }
  const q = (document.getElementById('avatarSearch')?.value || '').toLowerCase();
  let rows = DATA.avatars.filter(a => {
    if (!q) return true;
    const hay = [a.name, a.collection_id, a.description, a.model_file_url].join(' ').toLowerCase();
    return hay.includes(q);
  }).slice(0, 500);
  document.getElementById('avatarCount').textContent = `${rows.length} of ${DATA.avatars.length} shown`;
  document.getElementById('avatarGrid').innerHTML = rows.map(a => `<div class="avatar-card">
    ${a.thumbnail_url ? `<img src="${esc(a.thumbnail_url)}" loading="lazy" alt="${esc(a.name || a.collection_id)}" onerror="this.style.display='none'">` : ''}
    <h4>${esc(a.name)}</h4>
    <div class="mono">${esc(a.collection_id)}</div>
    ${a.model_file_url ? `<a href="${esc(a.model_file_url)}" target="_blank">Download VRM</a>` : ''}
  </div>`).join('');
}

function filterOS() {
  if (!_openseaLoaded) {
    document.getElementById('osBody').innerHTML = '<tr><td colspan="12" class="loading-msg">Loading OpenSea candidates...</td></tr>';
    loadOpensea();
    return;
  }
  const q = document.getElementById('search').value.toLowerCase();
  let rows = DATA.opensea.filter(c => {
    if (q) {
      const hay = [c.slug, c.name, c.contract, c.vrm_url].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  rows.sort((a, b) => {
    let va = a[sortKeyOS] || '', vb = b[sortKeyOS] || '';
    return sortAscOS ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
  });
  document.getElementById('osBody').innerHTML = rows.map(c => {
    const us = c.url_status;
    const urlIcon = us === 'alive' ? '✓' : us === 'dead' ? '✗' : us === 'error' ? '?' : '—';
    const urlColor = us === 'alive' ? '#56d364' : us === 'dead' ? '#f85149' : '#8b949e';
    const wbLink = c.wayback_available ? ` <a href="https://web.archive.org/web/*/opensea.io/collection/${c.slug}" target="_blank" title="${c.wayback_snapshots} snapshots">📦</a>` : '';
    const ds = c.discord_status;
    let dIcon = '—', dColor = '#8b949e', dTitle = '';
    if (ds === 'alive') { dIcon = '✓'; dColor = '#56d364'; dTitle = `${c.discord_members||0} members`; }
    else if (ds === 'dead') { dIcon = '✗'; dColor = '#f85149'; dTitle = 'expired/revoked'; }
    else if (ds === 'rate_limited') { dIcon = '⏳'; dColor = '#d29922'; }
    const osImg = c.image_url ? `<img class="thumb" src="${c.image_url}" alt="${esc(c.name)}" onclick="showImg('${c.image_url}','${esc(c.name)}','${c.banner_image_url || ''}')" onerror="this.outerHTML='<span class=\'thumb-placeholder\'>🖼</span>'">` : '<span class="thumb-placeholder">🖼</span>';
    const osVrmBtn = c.vrm_url_https ? `<button class="vrm-btn" onclick="openVrmViewer('${c.vrm_url_https}','${esc(c.name)}','${esc(c.vrm_url_https)}')">▶ VRM</button>` : '—';
    const osTw = c.twitter_username ? ` <a href="https://twitter.com/${c.twitter_username}" target="_blank" title="@${c.twitter_username}">𝕏</a>` : '';
    return `<tr>
    <td>${osImg}</td>
    <td>${c.slug ? `<a href="https://opensea.io/collection/${c.slug}" target="_blank">${esc(c.slug)}</a>` : '—'}</td>
    <td>${esc(c.name)}</td>
    <td class="mono">${esc(c.release_date || '?')}</td>
    <td>${esc(c.chain || '?')}</td>
    <td>${badge(c.status === 'vrm' ? 'green' : c.status === 'no_vrm' ? 'unknown' : 'yellow', c.status)}</td>
    <td style="color:${urlColor}">${urlIcon}${wbLink}</td>
    <td style="color:${dColor}" title="${dTitle}">${dIcon}${osTw}</td>
    <td class="mono">${esc(c.vrm_param || '—')}</td>
    <td>${osVrmBtn}</td>
    <td class="mono">${c.contract ? `<a href="https://etherscan.io/address/${c.contract}" target="_blank">${c.contract.slice(0,8)}..</a>` : '—'}</td>
    <td class="mono">${esc(c.source_query || '—')}</td>
  </tr>`}).join('');
}

function sort(key) { sortKey = key; sortAsc = !sortAsc; filter(); }
function sortOS(key) { sortKeyOS = key; sortAscOS = !sortAscOS; filterOS(); }

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('collectionsView').style.display = tab === 'collections' ? '' : 'none';
  document.getElementById('avatarsView').style.display = tab === 'avatars' ? '' : 'none';
  document.getElementById('openseaView').style.display = tab === 'opensea' ? '' : 'none';
  if (tab === 'avatars') filterAvatars();
  if (tab === 'opensea') filterOS();
}

// ─── Image preview modal ───────────────────────────────────────────────────
function showImg(url, name, bannerUrl) {
  if (!url) return;
  const img = document.getElementById('imgModalImg');
  const banner = document.getElementById('imgModalBanner');
  const label = document.getElementById('imgModalLabel');
  img.src = url;
  img.alt = name || '';
  // Handle video banners (OpenSea allows .mp4 banners)
  const isVideo = bannerUrl && (bannerUrl.includes('.mp4') || bannerUrl.includes('stream.mux.com'));
  if (bannerUrl && !isVideo) {
    banner.src = bannerUrl;
    banner.style.display = '';
  } else {
    banner.style.display = 'none';
    banner.src = '';
  }
  label.textContent = name || '';
  document.getElementById('imgModal').classList.add('active');
}
function closeImgModal() {
  document.getElementById('imgModal').classList.remove('active');
  document.getElementById('imgModalImg').src = '';
  document.getElementById('imgModalBanner').src = '';
}

// ─── VRM viewer modal (Three.js + @pixiv/three-vrm via ES modules) ──────────
// The VRM viewer is loaded as an ES module. Functions are exposed on window.
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
    // Load the ES module script
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

          // Orbit controls via mouse
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

            // Reset pose
            vrm.humanoid?.resetNormalizedPose();
            // Face forward
            if (vrm.humanoid) {
              vrm.humanoid.setNormalizedPose();
            }

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
      // If a URL is already queued, init now
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

// Escape to close modals
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeVrmModal(); closeImgModal(); }
});

// ─── Init: fetch build-info, then load collections + summary ────────────────
(async () => {
  try {
    await loadBuildInfo();
    await loadCollections();
  } catch (err) {
    document.getElementById('collectionsBody').innerHTML =
      `<tr><td colspan="21" class="loading-msg">Failed to load catalog data: ${esc(err.message)}<br>Run <code>python scripts/build_catalog.py</code> to generate data files.</td></tr>`;
    console.error(err);
  }
})();

// ─── Service worker registration (offline cache for hashed static files) ────
// Only register on https or localhost — never on file:// or other origins.
if ('serviceWorker' in navigator) {
  const swScope = location.protocol === 'https:' || location.hostname === 'localhost'
    ? './sw.js'
    : null;
  if (swScope) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register(swScope).catch((err) => {
        console.warn('sw registration failed:', err);
      });
    });
  }
}
