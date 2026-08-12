(() => {
  function escHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function loadEvidenceRows() {
    const infoResp = await fetch('data/build-info.json', { cache: 'no-store' });
    if (!infoResp.ok) throw new Error(`build info ${infoResp.status}`);
    const info = await infoResp.json();
    const collResp = await fetch(`data/${info.files.collections}`, { cache: 'no-store' });
    if (!collResp.ok) throw new Error(`collections ${collResp.status}`);
    const payload = await collResp.json();
    return payload.collections || [];
  }

  function ensureSummary(rows) {
    const bar = document.querySelector('.result-bar');
    if (!bar) return;
    let summary = document.getElementById('crawlSummary');
    if (!summary) {
      summary = document.createElement('span');
      summary.id = 'crawlSummary';
      summary.className = 'result-count crawl-summary';
      summary.setAttribute('aria-live', 'polite');
      bar.appendChild(summary);
    }

    const crawled = rows.filter((r) => Number(r.evidence_sources || 0) > 0);
    const sources = rows.reduce((n, r) => n + Number(r.evidence_sources || 0), 0);
    const corroborations = rows.reduce((n, r) => n + Number(r.evidence_corroborated || 0), 0);
    const conflicts = rows.reduce((n, r) => n + Number(r.evidence_conflicts || 0), 0);
    const tokens = rows.reduce((n, r) => n + Number(r.evidence_tokens_sampled || 0), 0);
    const uris = rows.reduce((n, r) => n + Number(r.evidence_uris_observed || 0), 0);
    const ready = rows.reduce((n, r) => n + Number(r.promotion_candidate_count || 0), 0);

    summary.textContent = `${crawled.length}/${rows.length} crawled · ${sources} source observations · ${corroborations} corroborations · ${conflicts} conflicts · ${tokens} token samples · ${uris} URIs · ${ready} promotion-ready`;
  }

  function evidenceText(row) {
    const sources = Number(row.evidence_sources || 0);
    if (!sources) return '';
    const corroborated = Number(row.evidence_corroborated || 0);
    const conflicts = Number(row.evidence_conflicts || 0);
    const tokens = Number(row.evidence_tokens_sampled || 0);
    const uris = Number(row.evidence_uris_observed || 0);
    const models = Number(row.evidence_model_signals || 0);
    const ready = Number(row.promotion_candidate_count || 0);
    const bits = [`Crawled ${sources} source${sources === 1 ? '' : 's'}`];
    if (corroborated) bits.push(`${corroborated} corroborated`);
    if (conflicts) bits.push(`${conflicts} conflict${conflicts === 1 ? '' : 's'}`);
    if (tokens) bits.push(`${tokens} token samples`);
    if (uris) bits.push(`${uris} URIs`);
    if (models) bits.push(`${models} model signals`);
    if (ready) bits.push(`${ready} promotion-ready`);
    return bits.join(' · ');
  }

  function decorateRows(rows) {
    const byName = new Map(rows.map((row) => [String(row.name || ''), row]));
    for (const article of document.querySelectorAll('.crow[aria-label]')) {
      const row = byName.get(article.getAttribute('aria-label') || '');
      if (!row) continue;
      const text = evidenceText(row);
      if (!text) continue;
      let target = article.querySelector('.crawl-evidence-visible');
      if (!target) {
        target = document.createElement('div');
        target.className = 'crawl-evidence-visible';
        target.style.fontSize = '12px';
        target.style.marginTop = '4px';
        target.style.opacity = '0.78';
        const main = article.querySelector('.crow-main');
        if (main) main.appendChild(target);
      }
      target.innerHTML = `<span title="Last crawler evidence: ${escHtml(row.evidence_last_seen || 'unknown')}">${escHtml(text)}</span>`;
    }
  }

  async function boot() {
    try {
      const rows = await loadEvidenceRows();
      ensureSummary(rows);
      const grid = document.getElementById('collectionsGrid');
      if (!grid) return;
      const render = () => decorateRows(rows);
      render();
      const observer = new MutationObserver(render);
      observer.observe(grid, { childList: true, subtree: true });
    } catch (error) {
      console.warn('crawl evidence UI failed', error);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
