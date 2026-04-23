/**
 * Types matching the avatar-api (port 1233) response shapes.
 * These are the live API types — distinct from altiico's static-data Avatar type.
 */

export interface ApiCollection {
  slug: string;
  name: string;
  description: string;
  license: string;
  avatar_count: number;
  banner_url: string;
  pfp_url: string;
  source: string;
  contract: string | null;
  status: 'draft' | 'ingesting' | 'staged' | 'published' | 'archived';
}

export interface ApiAvatar {
  id: number;
  name: string;
  token_id: string;
  image_url: string;
  thumbnail_url: string;
  original_vrm_url: string | null;
  optimized_vrm_url: string | null;
  collection_name: string;
  collection_slug: string;
  contract: string | null;
  chain: string;
  license: string;
  collection_license: string;
  contentRating: string | null;
}

/** Preferred VRM URL: optimized if available, else original */
export function getVrmUrl(avatar: ApiAvatar): string | null {
  return avatar.optimized_vrm_url ?? avatar.original_vrm_url ?? null;
}
