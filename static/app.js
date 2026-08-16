// Data loading (lazy, content-hashed JSON files)
let DATA = { collections: [] };
let BUILD_INFO = null;
let _collRows = [];
let _filterTimer = null;
let lastFocusedElement = null;

async function fetchJSON(path, timeoutMs = 20000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(path, { signal: controller.signal });
    if (!resp.ok) throw new Error(`Failed to load ${path}: ${resp.status}`);
    return await resp.json();
  } catch (error) {
    if (error && error.name === 'AbortError') {
      throw new Error(`Timed out loading ${path}`);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
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

function esc(value) {
  return value
    ? String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
    : '';
}

function licenseBadge(category, collection) {
  const labels = {
    green: 'Open use',
    yellow: 'Holder-gated',
    red: 'Restricted',
    unknown: 'License unknown',
  };
  const key = category || 'unknown';
  const label = labels[key] || labels.unknown;
  const actual = (collection && collection.vrm_license || '').trim();
  const reasons = collection && collection.reason_codes || [];
  const confidence = collection && collection.license_confidence || 'unknown';
  const detail = [actual || label];
  if (reasons.length) detail.push(reasons.join(', '));
  detail.push(`confidence: ${confidence}`);
  return `<span class="badge badge-${esc(key)}" title="${esc(detail.join(' — '))}">${esc(label)}</span>`;
}

function supplyText(collection) {
  if (!collection.total_supply) return null;
  const note = collection.mint_status === 'ongoing' ? ' minting' : ' items';
  return `${collection.total_supply.toLocaleString()}${note}`;
}

const CHAIN_NAMES = {
  ethereum: 'Ethereum',
  base: 'Base',
  polygon: 'Polygon',
  optimism: 'Optimism',
  arbitrum: 'Arbitrum',
  shape: 'Shape',
  ape_chain: 'ApeChain',
  zora: 'Zora',
  multi: 'Multi-chain',
};

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

function explorerFor(chain, address) {
  const explorer = EXPLORERS[(chain || '').toLowerCase()];
  return explorer ? { url: explorer[0] + address, name: explorer[1] } : null;
}

function storageOf(collection) {
  const url = collection.vrm_check_url || collection.vrm_url_https || collection.vrm_url_pattern || '';
  if (!url) return null;

  const ipfsScheme = /^ipfs:\/\/([^/]+)(\/.*)?$/i.exec(url);
  const ipfsGateway = /\/ipfs\/([A-Za-z0-9]+)(\/.*)?$/.exec(url);
  if (ipfsScheme || ipfsGateway) {
    const match = ipfsScheme || ipfsGateway;
    const cid = match[1];
    const path = match[2] || '';
    return {
      kind: 'IPFS',
      href: `https://ipfs.io/ipfs/${cid}${path}`,
      detail: `${cid}${path}`,
    };
  }

  const arweaveGateway = /arweave\.net\/([A-Za-z0-9_-]{43})/.exec(url);
  if (arweaveGateway || url.toLowerCase().startsWith('ar://')) {
    const transaction = arweaveGateway ? arweaveGateway[1] : url.slice(5);
    return {
      kind: 'Arweave',
      href: `https://viewblock.io/arweave/tx/${transaction}`,
      detail: transaction,
    };
  }

  if (url.toLowerCase().includes('githubusercontent') || url.toLowerCase().includes('github.com')) {
    return { kind: 'GitHub', href: url, detail: url };
  }

  try {
    return {
      kind: new URL(url).hostname.replace(/^www\./, ''),
      href: url,
      detail: url,
    };
  } catch {
    return null;
  }
}

function collectionLinks(collection) {
  const links = [];
  if (collection.opensea_slug) {
    links.push(`<a class="icon-link" href="https://opensea.io/collection/${encodeURIComponent(collection.opensea_slug)}" target="_blank" rel="noopener">OpenSea</a>`);
  }
  if (collection.project_url) {
    links.push(`<a class="icon-link" href="${esc(collection.project_url)}" target="_blank" rel="noopener">Site</a>`);
  }
  if (collection.twitter_username) {
    links.push(`<a class="icon-link" href="https://twitter.com/${esc(collection.twitter_username)}" target="_blank" rel="noopener" aria-label="${esc(collection.name)} on X">X</a>`);
  }
  if (collection.discord_url && collection.discord_status === 'alive') {
    links.push(`<a class="icon-link" href="${esc(collection.discord_url)}" target="_blank" rel="noopener">Discord</a>`);
  }
  return links.length ? `<span class="ccard-links">${links.join('')}</span>` : '';
}

function evidenceLinks(collection) {
  const items = [];
  const contracts = collection.contracts && collection.contracts.length
    ? collection.contracts
    : (collection.contract ? [{ address: collection.contract, chain: collection.chain }] : []);
  const chain = collection.chain || (contracts[0] && contracts[0].chain);

  if (chain) {
    items.push(`<span>${esc(CHAIN_NAMES[chain] || chain)}</span>`);
  }

  if (contracts.length) {
    const first = contracts[0];
    const address = first.address;
    const explorer = address && explorerFor(first.chain || chain, address);
    const label = contracts.length > 1 ? `${contracts.length} contracts` : 'Contract';
    if (explorer) {
      items.push(`<a href="${esc(explorer.url)}" target="_blank" rel="noopener" title="${esc(address)} — open on ${esc(explorer.name)}">${esc(label)}</a>`);
    } else {
      items.push(`<span title="${esc(address || '')}">${esc(label)}</span>`);
    }
  }

  const storage = storageOf(collection);
  if (storage) {
    items.push(`<a href="${esc(storage.href)}" target="_blank" rel="noopener" title="${esc(storage.detail)}">${esc(storage.kind)}</a>`);
  }

  if (!items.length) return '';
  return `<span class="evidence">${items.join('<span class="evidence-separator" aria-hidden="true">·</span>')}</span>`;
}

function onSearch() {
  clearTimeout(_filterTimer);
  _filterTimer = setTimeout(filter, 150);
}

function filterValues() {
  return {
    query: document.getElementById('search').value.trim().toLowerCase(),
    chain: document.getElementById('f-chain').value,
    license: document.getElementById('f-license').value,
    vrm: document.getElementById('f-vrm').value,
    sort: document.getElementById('f-sort').value || 'vrm',
  };
}

function updateFilterControls(values) {
  const advancedCount = [values.chain, values.license, values.vrm].filter(Boolean).length
    + (values.sort !== 'vrm' ? 1 : 0);
  const toggle = document.getElementById('filterToggle');
  toggle.textContent = advancedCount ? `Filters (${advancedCount})` : 'Filters';
  document.getElementById('clearFilters').hidden = !(
    values.query || advancedCount
  );
}

function toggleFilters() {
  const panel = document.getElementById('filterPanel');
  const toggle = document.getElementById('filterToggle');
  const opening = panel.hidden;
  panel.hidden = !opening;
  toggle.setAttribute('aria-expanded', String(opening));
  if (opening) {
    requestAnimationFrame(() => document.getElementById('f-chain').focus());
  }
}

function clearFilters() {
  document.getElementById('search').value = '';
  document.getElementById('f-chain').value = '';
  document.getElementById('f-license').value = '';
  document.getElementById('f-vrm').value = '';
  document.getElementById('f-sort').value = 'vrm';
  document.getElementById('filterPanel').hidden = true;
  document.getElementById('filterToggle').setAttribute('aria-expanded', 'false');
  filter();
  document.getElementById('search').focus();
}

function applyCollectionFilters(values) {
  let rows = DATA.collections.filter((collection) => {
    if (values.chain && collection.chain !== values.chain) return false;
    if (values.license && (collection.license_category || 'unknown') !== values.license) return false;
    if (values.vrm === 'live' && collection.vrm_check_status !== 'ok_vrm') return false;
    if (values.vrm === 'dead' && collection.vrm_reachable !== 0) return false;
    if (values.vrm === 'nourl' && collection.vrm_check_status !== 'no_url') return false;

    if (values.query) {
      const contracts = collection.contracts && collection.contracts.length
        ? collection.contracts.map((contract) => contract.address).join(' ')
        : collection.contract;
      const haystack = [
        collection.name,
        contracts,
        collection.opensea_slug,
        collection.vrm_license,
        collection.creator,
        collection.notes,
        collection.description,
        collection.curated_description,
        collection.vipe_category,
      ].join(' ').toLowerCase();
      if (!haystack.includes(values.query)) return false;
    }
    return true;
  });

  const vrmRank = { ok_vrm: 0, reachable_not_vrm: 1, no_url: 3 };
  rows.sort((a, b) => {
    if (values.sort === 'vrm') {
      return (vrmRank[a.vrm_check_status] ?? 2) - (vrmRank[b.vrm_check_status] ?? 2)
        || String(a.name).localeCompare(String(b.name));
    }
    if (values.sort === 'release_date') {
      return String(b.release_date || '').localeCompare(String(a.release_date || ''));
    }
    if (values.sort === 'total_supply') return (b.total_supply || 0) - (a.total_supply || 0);
    if (values.sort === 'avatars_total') return (b.avatars_total || 0) - (a.avatars_total || 0);
    return String(a.name || '').localeCompare(String(b.name || ''));
  });
  return rows;
}

function filter() {
  const values = filterValues();
  const rows = applyCollectionFilters(values);
  const total = DATA.collections.length;
  const verified = rows.filter((collection) => collection.vrm_check_status === 'ok_vrm').length;
  const noun = rows.length === 1 ? 'collection' : 'collections';

  _collRows = rows;
  document.getElementById('collCount').innerHTML =
    `<b>${rows.length}</b> ${noun}${rows.length !== total ? ` of ${total}` : ''} · ${verified} verified`;
  document.getElementById('emptyState').style.display = rows.length ? 'none' : 'block';
  document.getElementById('collectionsGrid').innerHTML = rows.map(collectionRow).join('');
  updateFilterControls(values);
}

function isVideoUrl(url) {
  return !!url && (url.includes('.mp4') || url.includes('stream.mux.com') || url.includes('.m3u8'));
}

function vrmStatus(collection) {
  const status = collection.vrm_check_status;
  if (status === 'ok_vrm') {
    const size = collection.vrm_check_bytes
      ? `${(collection.vrm_check_bytes / 1048576).toFixed(1)} MB`
      : '';
    const title = [
      'A sample file was fetched and parsed as VRM',
      size,
      collection.vrm_check_url || '',
    ].filter(Boolean).join(' — ');
    return `<span class="badge vrm-live" title="${esc(title)}">Verified</span>`;
  }
  if (status === 'reachable_not_vrm') {
    const notes = String(collection.notes || collection.short_description || '').toLowerCase();
    const glb = notes.includes('glb');
    const label = glb ? 'GLB, not VRM' : 'Not a VRM';
    const title = glb
      ? 'A file was fetched. It is a GLB without a VRM / VRMC_vrm extension. The VRM, if it exists, is not at this URL.'
      : 'A file was fetched, but it is not a valid VRM. There is no VRM / VRMC_vrm extension at this URL.';
    return `<span class="badge vrm-warn" title="${esc(title)}">${label}</span>`;
  }
  if (status === 'no_url') {
    return '<span class="badge vrm-none" title="No VRM file URL is recorded">No file</span>';
  }
  if (collection.vrm_reachable === 0) {
    const detail = `${status || 'request failed'}${collection.vrm_check_http ? ` ${collection.vrm_check_http}` : ''}`;
    return `<span class="badge vrm-dead" title="${esc(detail)}">Unavailable</span>`;
  }
  if (collection.vrm_url_https) {
    return '<span class="badge vrm-pending" title="A file URL exists but has not passed VRM validation">Unchecked</span>';
  }
  return '<span class="badge vrm-none">No file</span>';
}

function vrmAction(collection, index) {
  if (collection.vrm_check_status === 'ok_vrm' && collection.vrm_url_https) {
    return `<button class="vrm-btn" type="button" data-vrm="${index}" aria-label="View ${esc(collection.name)} in the VRM viewer">View</button>`;
  }
  if (collection.vrm_url_https) {
    return `<a class="file-link" href="${esc(collection.vrm_url_https)}" target="_blank" rel="noopener">File</a>`;
  }
  return '';
}

function collectionRow(collection, index) {
  const letter = esc((collection.name || '?').trim().charAt(0).toUpperCase() || '?');
  const art = collection.image_url || collection.sample_nft_image
    || (collection.banner_image_url && !isVideoUrl(collection.banner_image_url)
      ? collection.banner_image_url
      : null);
  const thumb = art
    ? `<img loading="lazy" src="${esc(art)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'crow-fallback',textContent:'${letter}'}))">`
    : `<div class="crow-fallback" aria-hidden="true">${letter}</div>`;

  const facts = [];
  if (collection.release_date) facts.push(esc(String(collection.release_date).slice(0, 4)));
  const supply = supplyText(collection);
  if (supply) facts.push(supply);

  const files = collection.avatars_total || 0;
  const reachable = collection.avatars_reachable || 0;
  if (!supply && files) facts.push(`${files.toLocaleString()} files`);
  if (files) {
    const className = reachable === files ? 'av-all' : 'av-part';
    const label = reachable === files
      ? `${files.toLocaleString()} files reachable`
      : `${reachable.toLocaleString()}/${files.toLocaleString()} files reachable`;
    facts.push(`<span class="${className}">${label}</span>`);
  }

  const description = collection.curated_description || collection.description || '';
  const line3 = facts.length || description
    ? `<div class="crow-line3">
        ${facts.length ? `<span class="crow-facts">${facts.join(' · ')}</span>` : ''}
        ${description ? `<span class="crow-desc">${esc(description)}</span>` : ''}
      </div>`
    : '';

  return `<article class="crow" role="listitem" aria-label="${esc(collection.name)}">
    <div class="crow-thumb" aria-hidden="true">${thumb}</div>
    <div class="crow-main">
      <div class="crow-line1">
        <span class="crow-name">${esc(collection.name)}</span>
        ${collection.creator ? `<span class="crow-creator">${esc(collection.creator)}</span>` : ''}
      </div>
      <div class="crow-line2">
        ${vrmStatus(collection)}
        ${licenseBadge(collection.license_category, collection)}
        ${evidenceLinks(collection)}
      </div>
      ${line3}
    </div>
    <div class="crow-actions">
      ${collectionLinks(collection)}
      ${vrmAction(collection, index)}
    </div>
  </article>`;
}

function wireDelegation() {
  document.getElementById('collectionsView').addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-vrm]');
    if (!trigger) return;
    const collection = _collRows[Number(trigger.dataset.vrm)];
    if (collection && collection.vrm_url_https) {
      openVrmViewer(collection.vrm_url_https, collection.name);
    }
  });
}

function wireModal() {
  const modal = document.getElementById('vrmModal');
  modal.addEventListener('click', (event) => {
    if (event.target === modal) closeVrmModal();
  });
}

// VRM viewer (Three.js + @pixiv/three-vrm via ES modules)
function showVrmError(message) {
  document.getElementById('vrmLoading').classList.remove('active');
  const error = document.getElementById('vrmError');
  error.textContent = message;
  error.classList.add('active');
}
window._showVrmError = showVrmError;

function openVrmViewer(vrmUrl, name) {
  if (!vrmUrl) return;

  const modal = document.getElementById('vrmModal');
  lastFocusedElement = document.activeElement;
  modal.classList.add('active');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
  window._vrmModalOpen = true;
  document.getElementById('vrmModalTitle').textContent = name || 'VRM viewer';

  const loading = document.getElementById('vrmLoading');
  loading.textContent = 'Loading VRM…';
  loading.classList.add('active');
  document.getElementById('vrmError').classList.remove('active');
  document.getElementById('vrmFooterInfo').textContent = 'Reading model metadata…';
  document.getElementById('vrmFooterLink').href = vrmUrl;
  requestAnimationFrame(() => document.getElementById('vrmModalClose').focus());

  if (window._vrmResize) requestAnimationFrame(() => window._vrmResize());

  if (window._vrmViewerReady) {
    window._initVrmScene(vrmUrl);
    return;
  }

  window._pendingVrmUrl = vrmUrl;
  if (window._vrmViewerLoading) return;
  window._vrmViewerLoading = true;

  const script = document.createElement('script');
  script.type = 'module';
  script.onerror = () => {
    window._vrmViewerLoading = false;
    window._showVrmError('Could not start the VRM viewer. Open the file directly instead.');
  };
  script.textContent = `
    import * as THREE from 'three';
    import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
    import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

    let scene = null;
    let renderer = null;
    let camera = null;
    let controls = null;
    let currentVrm = null;
    let clock = null;
    let animationFrame = null;

    function disposeCurrent() {
      if (currentVrm) {
        scene.remove(currentVrm.scene);
        VRMUtils.deepDispose(currentVrm.scene);
        currentVrm = null;
      }
    }

    function render() {
      if (!window._vrmModalOpen) {
        animationFrame = null;
        return;
      }
      animationFrame = requestAnimationFrame(render);
      const delta = clock.getDelta();
      if (currentVrm) currentVrm.update(delta);
      if (controls) controls.update();
      renderer.render(scene, camera);
    }

    function startRender() {
      if (animationFrame === null) render();
    }

    function frameModel(vrm) {
      const box = new THREE.Box3().setFromObject(vrm.scene);
      const sphere = box.getBoundingSphere(new THREE.Sphere());
      const center = sphere.center;
      const radius = Math.max(sphere.radius, 0.05);
      const verticalFov = THREE.MathUtils.degToRad(camera.fov);
      const fitVertical = radius / Math.sin(verticalFov / 2);
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
      const fitHorizontal = radius / Math.sin(horizontalFov / 2);
      const distance = Math.max(fitVertical, fitHorizontal) * 1.25;
      camera.position.set(0, center.y, distance);
      camera.near = Math.max(0.01, distance / 500);
      camera.far = distance * 50;
      camera.updateProjectionMatrix();
      controls.target.copy(center);
      controls.target.x = 0;
      controls.update();
    }

    function resize() {
      const container = document.getElementById('vrmCanvasContainer');
      if (!container || !renderer || !camera) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }
    window.addEventListener('resize', resize);
    window._vrmResize = resize;

    function urlCandidates(url) {
      const candidates = [url];
      const match = /\\/ipfs\\/([A-Za-z0-9]+)(\\/.*)?$/.exec(url);
      if (match) {
        const cid = match[1];
        const path = match[2] || '';
        for (const gateway of [
          'https://ipfs.io',
          'https://dweb.link',
          'https://cloudflare-ipfs.com',
          'https://gateway.pinata.cloud',
        ]) {
          const alternate = gateway + '/ipfs/' + cid + path;
          if (!candidates.includes(alternate)) candidates.push(alternate);
        }
      }
      return candidates;
    }

    window._initVrmScene = function(vrmUrl) {
      const canvas = document.getElementById('vrmCanvas');
      const container = document.getElementById('vrmCanvasContainer');
      const width = container.clientWidth || 800;
      const height = container.clientHeight || 500;

      if (!scene) {
        scene = new THREE.Scene();
        clock = new THREE.Clock();
        camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 100);
        renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(width, height, false);
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        scene.add(new THREE.AmbientLight(0xffffff, 2.0));

        const keyLight = new THREE.DirectionalLight(0xffffff, 1.6);
        keyLight.position.set(1, 2, 2);
        scene.add(keyLight);

        const rimLight = new THREE.DirectionalLight(0x8899ff, 0.7);
        rimLight.position.set(-2, 1, -2);
        scene.add(rimLight);

        controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.1;
        controls.minDistance = 0.3;
        controls.maxDistance = 40;

      }

      resize();
      disposeCurrent();
      startRender();

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
            window._showVrmError('This file is glTF/GLB, but it contains no VRM extension.');
            return;
          }

          try { VRMUtils.removeUnnecessaryVertices(gltf.scene); } catch (error) {}
          try { VRMUtils.combineSkeletons(gltf.scene); } catch (error) {}
          try { VRMUtils.rotateVRM0(vrm); } catch (error) {}
          vrm.scene.traverse((object) => { object.frustumCulled = false; });

          currentVrm = vrm;
          scene.add(vrm.scene);
          frameModel(vrm);

          const clean = (value) => {
            const text = Array.isArray(value)
              ? value.filter(Boolean).join(', ')
              : (value == null ? '' : String(value));
            return (!text || text === 'undefined' || text === 'null') ? '' : text;
          };
          const meta = vrm.meta || {};
          const title = clean(meta.name) || clean(meta.title);
          const author = clean(meta.authors) || clean(meta.author);
          const spec = (meta.metaVersion === '1' || meta.licenseUrl) ? 'VRM 1.0' : 'VRM 0.x';
          const bits = [spec];
          if (title) bits.push(title);
          if (author) bits.push('by ' + author);
          const license = clean(meta.licenseName) || clean(meta.licenseUrl);
          if (license) bits.push(license);
          document.getElementById('vrmFooterInfo').textContent = bits.join(' · ');
          document.getElementById('vrmLoading').classList.remove('active');
        },
        (progress) => {
          const element = document.getElementById('vrmLoading');
          if (!element) return;
          if (progress && progress.total) {
            const percent = Math.round((progress.loaded / progress.total) * 100);
            element.textContent = 'Loading VRM… ' + percent + '%';
          } else if (progress && progress.loaded) {
            element.textContent = 'Loading VRM… ' + Math.round(progress.loaded / 1024) + ' KB';
          }
        },
        (error) => {
          attempt += 1;
          if (attempt < candidates.length) {
            const element = document.getElementById('vrmLoading');
            if (element) element.textContent = 'Trying another gateway…';
            tryLoad();
            return;
          }
          window._showVrmError(
            'Could not load this VRM: '
            + ((error && error.message) || 'network or CORS error')
            + (candidates.length > 1 ? ' (tried ' + candidates.length + ' gateways)' : '')
            + '. Open the file directly instead.'
          );
        }
      );
      tryLoad();
    };

    window._vrmDispose = disposeCurrent;
    window._vrmState = function() {
      if (!currentVrm) return { loaded: false };
      const box = new THREE.Box3().setFromObject(currentVrm.scene);
      const size = box.getSize(new THREE.Vector3());
      let meshes = 0;
      let visible = 0;
      currentVrm.scene.traverse((object) => {
        if (object.isMesh || object.isSkinnedMesh) {
          meshes += 1;
          if (object.visible) visible += 1;
        }
      });
      return {
        loaded: true,
        meshes,
        visible,
        height: +size.y.toFixed(2),
        width: +size.x.toFixed(2),
        camY: +camera.position.y.toFixed(2),
        camZ: +camera.position.z.toFixed(2),
        targetY: +controls.target.y.toFixed(2),
        inFrustum: (() => {
          camera.updateMatrixWorld();
          const matrix = new THREE.Matrix4().multiplyMatrices(
            camera.projectionMatrix,
            camera.matrixWorldInverse,
          );
          return new THREE.Frustum().setFromProjectionMatrix(matrix).intersectsBox(box);
        })(),
        canvas: renderer.domElement.width + 'x' + renderer.domElement.height,
      };
    };

    window._vrmViewerReady = true;
    window._vrmViewerLoading = false;
    if (window._pendingVrmUrl) {
      const url = window._pendingVrmUrl;
      window._pendingVrmUrl = null;
      window._initVrmScene(url);
    }
  `;
  document.head.appendChild(script);
}

function closeVrmModal() {
  const modal = document.getElementById('vrmModal');
  if (!modal.classList.contains('active')) return;

  modal.classList.remove('active');
  modal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');
  window._vrmModalOpen = false;
  window._pendingVrmUrl = null;
  if (window._vrmDispose) window._vrmDispose();
  document.getElementById('vrmLoading').classList.remove('active');
  document.getElementById('vrmError').classList.remove('active');

  const focusTarget = lastFocusedElement;
  lastFocusedElement = null;
  if (focusTarget && typeof focusTarget.focus === 'function') {
    requestAnimationFrame(() => focusTarget.focus());
  }
}

document.addEventListener('keydown', (event) => {
  const modal = document.getElementById('vrmModal');
  if (event.key === 'Escape' && modal.classList.contains('active')) {
    closeVrmModal();
    return;
  }

  if (event.key === 'Tab' && modal.classList.contains('active')) {
    const focusable = [...modal.querySelectorAll('button:not([disabled]), a[href]')];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
});

wireDelegation();
wireModal();

(async () => {
  try {
    await loadBuildInfo();
    await loadCollections();
  } catch (error) {
    document.getElementById('collectionsGrid').innerHTML =
      `<div class="loading-msg">Failed to load catalog data: ${esc(error.message)}<br>Run <code>python scripts/build_catalog.py</code> to generate data files.</div>`;
    console.error(error);
  }
})();

if ('serviceWorker' in navigator) {
  const swScope = location.protocol === 'https:' || location.hostname === 'localhost'
    ? './sw.js'
    : null;
  if (swScope) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register(swScope, { updateViaCache: 'none' }).catch((error) => {
        console.warn('sw registration failed:', error);
      });
    });
  }
}
