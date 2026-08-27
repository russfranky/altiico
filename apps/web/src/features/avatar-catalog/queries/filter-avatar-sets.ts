import type { AvatarCatalogQuery, AvatarSetSummary } from '../domain';

function normalizeSearch(value: string) {
  return value.trim().toLowerCase();
}

export function filterAvatarSets(items: readonly AvatarSetSummary[], query: AvatarCatalogQuery): AvatarSetSummary[] {
  const search = normalizeSearch(query.search ?? '');

  return items.filter((item) => {
    const searchable = [item.displayName, item.archiveCode, item.description, ...item.tags];
    const matchesSearch = !search || searchable.some((value) => normalizeSearch(value).includes(search));
    const matchesState = !query.state || query.state === 'all' || item.state === query.state;
    const matchesReadiness = !query.readiness || query.readiness === 'all' || item.readiness === query.readiness;
    return matchesSearch && matchesState && matchesReadiness;
  });
}
