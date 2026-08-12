(() => {
  const originalEvidenceLinks = window.evidenceLinks;
  if (typeof originalEvidenceLinks !== 'function') return;

  window.evidenceLinks = function collectionEvidenceLinks(collection) {
    const base = originalEvidenceLinks(collection);
    const sources = Number(collection.evidence_sources || 0);
    if (!sources) return base;

    const corroborated = Number(collection.evidence_corroborated || 0);
    const conflicts = Number(collection.evidence_conflicts || 0);
    const tokens = Number(collection.evidence_tokens_sampled || 0);
    const uris = Number(collection.evidence_uris_observed || 0);
    const models = Number(collection.evidence_model_signals || 0);
    const ready = Number(collection.promotion_candidate_count || 0);
    const lastSeen = collection.evidence_last_seen ? String(collection.evidence_last_seen).slice(0, 10) : 'unknown';

    const detail = [
      `${sources} evidence source${sources === 1 ? '' : 's'}`,
      `${corroborated} corroborated`,
      `${conflicts} conflict${conflicts === 1 ? '' : 's'}`,
      `${tokens} token samples`,
      `${uris} token URIs`,
      `${models} model signals`,
      `${ready} promotion-ready`,
      `last checked ${lastSeen}`,
    ].join(' · ');

    const crawl = `<span class="evidence" title="${esc(detail)}"><span>Crawl ${sources}</span>${corroborated ? `<span class="evidence-separator" aria-hidden="true">·</span><span>${corroborated}✓</span>` : ''}${conflicts ? `<span class="evidence-separator" aria-hidden="true">·</span><span>${conflicts} conflict${conflicts === 1 ? '' : 's'}</span>` : ''}</span>`;
    return base ? `${base}<span class="evidence-separator" aria-hidden="true">·</span>${crawl}` : crawl;
  };
})();
