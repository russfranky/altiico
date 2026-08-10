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
  setStat('stat-ready', DATA.collections.filter(c => c.ready === 1 && c.hubzz_status === 'absent' && c.owner_decision !== 'exclude').length);
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
let _avRows = [];

// ─── Research state: bookmarks / status / notes (persisted in localStorage) ──
const RESEARCH_KEY = 'vrmcat_research_v1';
const STATUSES = [
  { v: '', label: '— status —', dot: 'var(--text-muted)' },
  { v: 'shortlist', label: '⭐ Shortlist', dot: 'var(--warning)' },
  { v: 'onboard', label: '✅ To onboard', dot: 'var(--success)' },
  { v: 'reviewing', label: '🔍 Reviewing', dot: 'var(--accent-2)' },
  { v: 'pass', label: '🚫 Pass', dot: 'var(--error)' },
];
let RESEARCH = {};
try { RESEARCH = JSON.parse(localStorage.getItem(RESEARCH_KEY) || '{}'); } catch { RESEARCH = {}; }
function saveResearch() { try { localStorage.setItem(RESEARCH_KEY, JSON.stringify(RESEARCH)); } catch {} }
function rec(id) { return RESEARCH[id] || (RESEARCH[id] = {}); }
function isBookmarked(id) { return !!(RESEARCH[id] && RESEARCH[id].bm); }
function bookmarkCount() { return Object.values(RESEARCH).filter(r => r.bm).length; }
function toggleBookmark(id) { const r = rec(id); r.bm = !r.bm; saveResearch(); refreshBookmarkUi(); }
function setStatus(id, v) { rec(id).status = v; saveResearch(); refreshBookmarkUi(); }
function editNote(id, name) {
  const r = rec(id);
  const v = prompt('Note for ' + (name || id) + ':', r.note || '');
  if (v === null) return;
  r.note = v.trim(); saveResearch();
  if (currentTab === 'collections') filter();
}
function refreshBookmarkUi() {
  const el = document.getElementById('bm-count'); if (el) el.textContent = bookmarkCount();
  if (currentTab === 'collections') filter();
}

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
  const fBookmark = (document.getElementById('f-bookmark') || {}).value || '';
  const fStatus = (document.getElementById('f-status') || {}).value || '';
  const fVrm = (document.getElementById('f-vrm') || {}).value || '';
  const fReady = (document.getElementById('f-ready') || {}).value || '';
  let rows = DATA.collections.filter(c => {
    if (fReady === 'ready' && !(c.ready === 1 && c.hubzz_status === 'absent' && c.owner_decision !== 'exclude')) return false;
    if (fReady === 'declined' && c.owner_decision !== 'exclude') return false;
    if (fReady === 'inhubzz' && c.hubzz_status === 'absent') return false;
    if (fReady === 'near' && !(c.readiness_score >= 6 && c.ready !== 1)) return false;
    if (fTier && c.tier !== fTier) return false;
    if (fChain && c.chain !== fChain) return false;
    if (fLicense && (c.license_category || 'unknown') !== fLicense) return false;
    if (fMint && (c.mint_status || '') !== fMint) return false;
    if (fVrm === 'live' && c.vrm_check_status !== 'ok_vrm') return false;
    if (fVrm === 'dead' && c.vrm_reachable !== 0) return false;
    if (fVrm === 'nourl' && c.vrm_check_status !== 'no_url') return false;
    if (fBookmark === 'bookmarked' && !isBookmarked(c.id)) return false;
    if (fStatus && ((RESEARCH[c.id] && RESEARCH[c.id].status) || '') !== fStatus) return false;
    if (q) {
      const hay = [c.name, c.contract, c.opensea_slug, c.vrm_license, c.creator, c.notes, c.description, c.curated_description, c.vipe_category].join(' ').toLowerCase();
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

function isVideoUrl(u) { return !!u && (u.includes('.mp4') || u.includes('stream.mux.com') || u.includes('.m3u8')); }

function socialLinks(c) {
  const out = [];
  if (c.twitter_username) out.push(`<a class="soc" href="https://twitter.com/${esc(c.twitter_username)}" target="_blank" rel="noopener">𝕏 ${esc(c.twitter_username)}</a>`);
  if (c.discord_url && c.discord_status === 'alive') out.push(`<a class="soc" href="${esc(c.discord_url)}" target="_blank" rel="noopener">💬 Discord${c.discord_members ? ' ' + c.discord_members.toLocaleString() : ''}</a>`);
  if (c.project_url) out.push(`<a class="soc" href="${esc(c.project_url)}" target="_blank" rel="noopener">🌐 Site</a>`);
  if (c.opensea_slug) out.push(`<a class="soc" href="https://opensea.io/collection/${encodeURIComponent(c.opensea_slug)}" target="_blank" rel="noopener">⛵ OpenSea</a>`);
  return out.join('');
}

function statusSelect(id, i) {
  const cur = (RESEARCH[id] && RESEARCH[id].status) || '';
  const opts = STATUSES.map(s => `<option value="${s.v}"${s.v === cur ? ' selected' : ''}>${s.label}</option>`).join('');
  return `<select class="status-sel status-${cur || 'none'}" data-status="${i}" onclick="event.stopPropagation()">${opts}</select>`;
}

function hubzzBadge(c) {
  if (c.hubzz_status === 'onboarded')
    return `<span class="badge hz-in" title="Already live in Hubzz as '${esc(c.hubzz_slug || '')}' (${c.hubzz_optimized}/${c.hubzz_rows} optimized) — nothing to do">🏠 in Hubzz</span>`;
  if (c.hubzz_status === 'partial')
    return `<span class="badge hz-part" title="In Hubzz as '${esc(c.hubzz_slug || '')}' but only ${c.hubzz_optimized}/${c.hubzz_rows} optimized — needs finishing">◑ partial (${c.hubzz_optimized}/${c.hubzz_rows})</span>`;
  return '';
}

function readinessBadge(c) {
  // A set that is already in Hubzz is NOT an onboarding target — say so instead
  // of advertising it as "ready".
  if (c.owner_decision === 'exclude')
    return `<span class="badge rdy-excl" title="${esc(c.owner_decision_reason || 'Owner declined')}">🚫 declined</span>`;
  if (c.ready === 1 && c.hubzz_status === 'absent')
    return '<span class="badge rdy-ready" title="Meets every criterion and is NOT yet in Hubzz — onboard this">✅ NEW · ready</span>';
  if (c.ready === 1) return '<span class="badge rdy-done" title="Meets every criterion but is already in Hubzz">✔ ready (already in)</span>';
  if (c.readiness_score == null) return '';
  let crit = c.readiness_criteria;
  if (typeof crit === 'string') { try { crit = JSON.parse(crit); } catch { crit = null; } }
  const missing = crit ? ['vrm_ok', 'license_ok', 'identity_ok'].filter(k => !crit[k]) : [];
  return `<span class="badge rdy-partial" title="Readiness ${c.readiness_score}/8${missing.length ? ' — missing: ' + missing.join(', ') : ''}">◐ ${c.readiness_score}/8</span>`;
}

function vrmReachBadge(c) {
  const s = c.vrm_check_status;
  if (s === 'ok_vrm') {
    const kb = c.vrm_check_bytes ? ' ' + Math.round(c.vrm_check_bytes / 1024) + 'KB' : '';
    return `<span class="badge vrm-live" title="VRM fetched & valid (${esc(c.vrm_check_url || '')})">🟢 VRM live${kb}</span>`;
  }
  if (s === 'reachable_not_vrm') return '<span class="badge vrm-warn" title="File reachable but not a valid VRM/GLB">🟡 not a VRM</span>';
  if (s === 'no_url') return '<span class="badge vrm-none" title="No VRM URL on record — unknown where the VRM lives">⚫ no VRM URL</span>';
  if (c.vrm_reachable === 0) return `<span class="badge vrm-dead" title="Unreachable: ${esc(s || '')}${c.vrm_check_http ? ' ' + c.vrm_check_http : ''}">🔴 VRM dead</span>`;
  return '';
}

function collectionCard(c, i) {
  const id = c.id;
  const letter = esc((c.name || '?').trim().charAt(0).toUpperCase() || '?');
  // Real banner only if it's an image (Mux/mp4 video banners can't render in <img>);
  // otherwise fall back to the real pfp as a full-cover hero, then a gradient letter.
  const realBanner = (c.banner_image_url && !isVideoUrl(c.banner_image_url)) ? c.banner_image_url : null;
  const pfpSrc = c.image_url || c.sample_nft_image;
  const heroSrc = realBanner || pfpSrc;
  const hero = heroSrc
    ? `<img loading="lazy" src="${esc(heroSrc)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'fallback',textContent:'${letter}'}))">`
    : `<div class="fallback">${letter}</div>`;
  // Overlapping pfp circle only when the hero is a distinct banner image.
  const pfp = (realBanner && pfpSrc)
    ? `<img class="ccard-pfp" loading="lazy" src="${esc(pfpSrc)}" alt="" onerror="this.style.display='none'">`
    : '';
  const chips = [];
  if (c.chain) chips.push(`<span class="chip"><span class="k">⛓</span> ${esc(c.chain)}</span>`);
  const sup = supplyText(c); if (sup) chips.push(`<span class="chip">${sup}</span>`);
  if (c.floor_price) chips.push(`<span class="chip"><span class="k">floor</span> <b>${c.floor_price.toFixed(2)} ${esc(c.floor_price_symbol || '')}</b></span>`);
  if (c.avatar_count) chips.push(`<span class="chip"><span class="k">avatars</span> <b>${c.avatar_count.toLocaleString()}</b></span>`);
  if (c.vipe_category) chips.push(`<span class="chip vipe-cat" title="VIPE platform category">${esc(c.vipe_category)}</span>`);
  if (c.vipe_assets_3d) chips.push(`<span class="chip" title="How this collection ships 3D (VIPE)">${esc(c.vipe_assets_3d)}</span>`);
  const vrmBtn = c.vrm_url_https
    ? `<button class="vrm-btn" data-vrm="${i}">▶ View VRM</button>`
    : `<button class="vrm-btn ghost" disabled>No VRM</button>`;
  const vrmLic = c.vrm_license ? ` <span class="badge badge-unknown">${esc(c.vrm_license)}</span>` : '';
  const descText = c.curated_description || c.description;
  const desc = descText ? `<p class="ccard-desc">${esc(descText)}</p>` : '';
  const socials = socialLinks(c);
  const note = (RESEARCH[id] && RESEARCH[id].note) ? `<div class="ccard-note" data-note="${i}" title="Edit note">📝 ${esc(RESEARCH[id].note)}</div>` : '';
  const starred = isBookmarked(id);
  return `<div class="ccard${starred ? ' bookmarked' : ''}">
    <div class="ccard-banner" data-img="${i}">
      ${hero}
      <button class="bm-star${starred ? ' on' : ''}" data-bm="${i}" title="Bookmark">${starred ? '★' : '☆'}</button>
      <div class="ccard-tier">${tierBadge(c.tier)}</div>
      ${pfp}
    </div>
    <div class="ccard-body">
      <div class="ccard-title">
        <span class="ccard-name">${esc(c.name)}</span>
        ${c.creator ? `<span class="ccard-creator">by ${esc(c.creator)}</span>` : ''}
      </div>
      <div class="ccard-badges">${readinessBadge(c)}${hubzzBadge(c)}${vrmReachBadge(c)}${licenseBadge(c.license_category, c)}${vrmLic}</div>
      ${chips.length ? `<div class="ccard-chips">${chips.join('')}</div>` : ''}
      ${desc}
      ${socials ? `<div class="ccard-socials">${socials}</div>` : ''}
      ${note}
      <div class="ccard-foot">
        ${vrmBtn}
        ${statusSelect(id, i)}
        <button class="note-btn" data-note="${i}" title="Add note">📝</button>
      </div>
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
function collById(id) {
  if (!window._collIndex) {
    window._collIndex = {};
    for (const c of DATA.collections) window._collIndex[c.id] = c;
  }
  return window._collIndex[id] || {};
}

const LICENSE_LABEL = { green: '🟢 CC0 / open', yellow: '🟡 Holder', red: '🔴 Restricted', unknown: '? Unknown' };

let _avPage = 0;
const AV_PAGE = 200;

function avatarFilters() {
  const q = (document.getElementById('search').value || '').toLowerCase();
  const fc = (document.getElementById('f-av-collection') || {}).value || '';
  const fl = (document.getElementById('f-av-license') || {}).value || '';
  return DATA.avatars.filter(a => {
    if (fc && a.collection_id !== fc) return false;
    if (fl) {
      const cat = collById(a.collection_id).license_category || 'unknown';
      if (fl === 'open' && cat !== 'green') return false;
      if (fl !== 'open' && cat !== fl) return false;
    }
    if (q) {
      const hay = [a.name, a.collection_id, a.description].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function populateAvatarCollectionFilter() {
  const sel = document.getElementById('f-av-collection');
  if (!sel || sel.dataset.filled) return;
  const counts = {};
  for (const a of DATA.avatars) counts[a.collection_id] = (counts[a.collection_id] || 0) + 1;
  const opts = Object.entries(counts).sort((x, y) => y[1] - x[1])
    .map(([id, n]) => `<option value="${esc(id)}">${esc(collById(id).name || id)} (${n})</option>`).join('');
  sel.innerHTML = '<option value="">All collections</option>' + opts;
  sel.dataset.filled = '1';
}

function filterAvatars(resetPage = true) {
  if (!_avatarsLoaded) {
    document.getElementById('avatarGrid').innerHTML = '<div class="loading-msg">Loading avatars…</div>';
    loadAvatars();
    return;
  }
  populateAvatarCollectionFilter();
  if (resetPage) _avPage = 0;
  const rows = avatarFilters();
  _avRows = rows;
  const shown = rows.slice(0, (_avPage + 1) * AV_PAGE);
  const openCount = rows.filter(a => (collById(a.collection_id).license_category) === 'green').length;
  document.getElementById('avatarCount').innerHTML =
    `<b>${rows.length.toLocaleString()}</b> avatars${rows.length !== DATA.avatars.length ? ' of ' + DATA.avatars.length.toLocaleString() : ''}` +
    ` · <span style="color:var(--success)">${openCount.toLocaleString()} CC0/open</span>` +
    ` · showing ${shown.length.toLocaleString()}`;

  document.getElementById('avatarGrid').innerHTML = shown.map((a, i) => {
    const c = collById(a.collection_id);
    const cat = c.license_category || 'unknown';
    const lic = LICENSE_LABEL[cat] || LICENSE_LABEL.unknown;
    return `<div class="avatar-card">
      <div class="thumb-box" data-avpreview="${i}" title="Preview VRM in 3D">
        ${a.thumbnail_url ? `<img loading="lazy" src="${esc(a.thumbnail_url)}" alt="" onerror="this.parentNode.textContent='🖼'">` : '🖼'}
        <span class="av-play">▶</span>
      </div>
      <h4 title="${esc(a.name || '')}">${esc(a.name || '—')}</h4>
      <div class="av-coll">${esc(c.name || a.collection_id)}</div>
      <div class="av-row">
        <span class="badge badge-${cat}" title="License of the parent collection">${lic}</span>
      </div>
      <div class="av-actions">
        <button class="av-btn" data-avpreview="${i}">▶ 3D</button>
        <button class="av-btn" data-avcopy="${i}" title="Copy VRM URL">⧉</button>
        <a class="av-btn" href="${esc(a.model_file_url)}" target="_blank" rel="noopener" title="Open/download VRM">↓</a>
      </div>
    </div>`;
  }).join('');

  const more = document.getElementById('avMore');
  if (more) more.style.display = shown.length < rows.length ? '' : 'none';
}

function avatarsShowMore() { _avPage++; filterAvatars(false); }

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
  const collView = document.getElementById('collectionsView');
  collView.addEventListener('click', e => {
    const bm = e.target.closest('[data-bm]');
    if (bm) { e.stopPropagation(); const c = _collRows[+bm.dataset.bm]; if (c) toggleBookmark(c.id); return; }
    const nb = e.target.closest('[data-note]');
    if (nb) { const c = _collRows[+nb.dataset.note]; if (c) editNote(c.id, c.name); return; }
    const v = e.target.closest('[data-vrm]');
    if (v) { const c = _collRows[+v.dataset.vrm]; if (c && c.vrm_url_https) openVrmViewer(c.vrm_url_https, c.name, c.vrm_url_https); return; }
    const im = e.target.closest('[data-img]');
    if (im) { const c = _collRows[+im.dataset.img]; if (c) { const src = c.image_url || c.sample_nft_image || c.banner_image_url; if (src && !isVideoUrl(src)) showImg(src, c.name, isVideoUrl(c.banner_image_url) ? null : c.banner_image_url); } }
  });
  collView.addEventListener('change', e => {
    const s = e.target.closest('[data-status]');
    if (s) { const c = _collRows[+s.dataset.status]; if (c) setStatus(c.id, s.value); }
  });
  document.getElementById('avatarsView').addEventListener('click', e => {
    const p = e.target.closest('[data-avpreview]');
    if (p) { const a = _avRows[+p.dataset.avpreview]; if (a) openVrmViewer(a.model_file_url, a.name || a.collection_id, a.model_file_url); return; }
    const cp = e.target.closest('[data-avcopy]');
    if (cp) { const a = _avRows[+cp.dataset.avcopy]; if (a) { navigator.clipboard.writeText(a.model_file_url); cp.textContent = '✓'; setTimeout(() => cp.textContent = '⧉', 1200); } }
  });
  document.getElementById('avatarsView').addEventListener('change', e => {
    if (e.target.id === 'f-av-collection' || e.target.id === 'f-av-license') filterAvatars();
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
{ const bc = document.getElementById('bm-count'); if (bc) bc.textContent = bookmarkCount(); }
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
