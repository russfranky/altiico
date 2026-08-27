import type { AvatarCatalogPort } from '../../ports/avatar-catalog';
import { filterAvatarSets } from '../../queries/filter-avatar-sets';
import { avatarSetDetailFixtures, toAvatarSetSummary } from './fixtures';
import { fixtureProvenance } from './fixtures/constants';
import { toLocalAvatarDetail } from './to-avatar-detail';

export const localAvatarCatalogAdapter: AvatarCatalogPort = {
  async listAvatarSets(query = {}) {
    const items = avatarSetDetailFixtures.map(toAvatarSetSummary);
    return { items: filterAvatarSets(items, query), provenance: fixtureProvenance };
  },

  async getAvatarSetBySlug(slug) {
    return avatarSetDetailFixtures.find((item) => item.slug === slug) ?? null;
  },

  async getAvatarByRoute(setSlug, avatarSlug) {
    const set = avatarSetDetailFixtures.find((item) => item.slug === setSlug);
    if (!set) return null;
    const slot = set.avatarSlots.find((item) => item.avatarSlug === avatarSlug);
    return slot ? toLocalAvatarDetail(set, slot) : null;
  },
};
