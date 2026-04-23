import { collections } from '../data/altiiData';
import type { Collection } from '../types';

/** Generate URL slug from collection name (e.g. "VIPE Heroes" -> "vipe-heroes") */
export function toCollectionSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

/** Find collection by slug (case-insensitive) */
export function getCollectionBySlug(slug: string): Collection | undefined {
  const normalized = slug.toLowerCase().replace(/_/g, '-');
  return collections.find(
    (c) => toCollectionSlug(c.name).toLowerCase() === normalized
  );
}

import type { Avatar } from '../types';

export function extractCollectionTraits(avatars: Avatar[]): Record<string, string[]> {
  const traits: Record<string, Set<string>> = {};
  for (const avatar of avatars) {
    if (avatar.traits) {
      for (const [key, value] of Object.entries(avatar.traits)) {
        if (!traits[key]) traits[key] = new Set();
        traits[key].add(String(value));
      }
    }
  }
  const result: Record<string, string[]> = {};
  for (const [key, values] of Object.entries(traits)) {
    result[key] = Array.from(values).sort();
  }
  return result;
}

export function filterCollectionAvatars(
  avatars: Avatar[],
  search: string,
  selectedTraits: Record<string, string>
): Avatar[] {
  return avatars.filter(avatar => {
    const matchesSearch = !search || avatar.name.toLowerCase().includes(search.toLowerCase());
    const matchesTraits = Object.entries(selectedTraits).every(([key, value]) => {
      if (!value) return true;
      return avatar.traits?.[key] === value;
    });
    return matchesSearch && matchesTraits;
  });
}
