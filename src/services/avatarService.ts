import * as Sentry from '@sentry/react';
import type { Avatar, Collection } from '../types';
import { getAvatars, collections as staticCollections, PLACEHOLDER_IMG } from '../data/altiiData';
import { API_BASE_URL } from '../config/api';
import { obs } from '../lib/obs';

/**
 * Report an avatar-api fetch failure to both Sentry and the local obs ring
 * buffer. Every avatarService catch path uses this so the fallback to
 * static data stays invisible in Sentry by default — but we always have
 * the signal. The fallback return is untouched at the call site; only the
 * catch body gains this call.
 */
function reportApiFailure(kind: string, endpoint: string, err: unknown): void {
    Sentry.captureException(err, {
        tags: { kind, 'api.endpoint': endpoint, 'api.method': 'GET' },
    });
    obs.exception(kind, err, { 'api.endpoint': endpoint, 'api.method': 'GET' });
}

const API_BASE = API_BASE_URL;

interface APIAvatarResponse {
  avatars: any[];
  total: number;
  limit: number;
  offset: number;
  has_more?: boolean;
}

interface APICollectionResponse {
  slug: string;
  name: string;
  avatar_count: number;
  banner_url?: string;
  pfp_url?: string;
  description?: string;
  contract?: string;
  source?: string;
  license?: string;
}

interface APICollectionsResponse {
  collections: APICollectionResponse[];
}

function mapApiAvatar(a: any): Avatar {
  // Only build OpenSea link when we have a real contract AND a numeric token ID
  const hasValidMarketLink = a.contract && a.token_id && a.token_id !== a.id;
  return {
    id: a.id,
    name: a.name,
    collection: a.collection_name || a.collection_slug || 'Unknown',
    image: a.image_url || a.thumbnail_url || PLACEHOLDER_IMG,
    vrm: a.original_vrm_url ? '3D Ready' : 'Pending',
    vrmUrl: a.optimized_vrm_url || a.original_vrm_url || undefined,
    opensea: hasValidMarketLink
      ? `https://opensea.io/assets/ethereum/${a.contract}/${a.token_id}`
      : '',
    license: a.license || a.collection_license || undefined,
    stats: a.triangles ? {
      triangles: a.triangles,
      fileSize: a.file_size_original,
      fileSizeOptimized: a.file_size_optimized,
    } : undefined,
    source: 'api',
  };
}

function mapApiCollection(c: APICollectionResponse): Collection {
  return {
    name: c.name,
    items: (c.avatar_count || 0).toLocaleString(),
    banner: c.banner_url || PLACEHOLDER_IMG,
    pfp: c.pfp_url || PLACEHOLDER_IMG,
    assets3D: (c.avatar_count || 0) > 0 ? '3D Ready' : 'Coming Soon',
    category: c.source === 'opensource' ? 'Open Source' : 'Ethereum',
    contract: c.contract,
    description: c.description,
    slug: c.slug,
    license: c.license,
  };
}

export interface SearchParams {
  search?: string;
  collection?: string;
  license?: string;
  limit?: number;
  offset?: number;
}

export const avatarService = {
  /**
   * Fetch all collections. Falls back to static data on failure.
   */
  getCollections: async (): Promise<Collection[]> => {
    try {
      const res = await fetch(`${API_BASE}/collections`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: APICollectionsResponse = await res.json();
      return data.collections.map(mapApiCollection);
    } catch (err) {
      reportApiFailure('api.collections', '/collections', err);
      return staticCollections as Collection[];
    }
  },

  /**
   * Fetch a single collection by its slug. Falls back to static data on failure.
   */
  getCollectionBySlug: async (slug: string): Promise<Collection | null> => {
    try {
      const res = await fetch(`${API_BASE}/collections/${encodeURIComponent(slug)}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      const c = data.collection || data;
      return mapApiCollection(c);
    } catch (err) {
      reportApiFailure('api.collection', `/collections/${slug}`, err);
      const { toCollectionSlug } = await import('../lib/collectionUtils');
      const match = staticCollections.find(
        (c) => toCollectionSlug(c.name) === slug.toLowerCase().replace(/_/g, '-')
      );
      return (match as Collection) ?? null;
    }
  },

  /**
   * Fetch avatars with full pagination support. Returns total count for UI.
   */
  getAvatars: async (params?: { limit?: number; offset?: number }): Promise<{ avatars: Avatar[]; total: number; has_more: boolean }> => {
    const limit = params?.limit || 60;
    const offset = params?.offset || 0;
    try {
      const res = await fetch(`${API_BASE}/avatars?limit=${limit}&offset=${offset}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: APIAvatarResponse = await res.json();
      return {
        avatars: data.avatars.map(mapApiAvatar),
        total: data.total,
        has_more: data.has_more || false,
      };
    } catch (err) {
      reportApiFailure('api.avatars', '/avatars', err);
      const all = getAvatars() as Avatar[];
      return { avatars: all.slice(offset, offset + limit), total: all.length, has_more: offset + limit < all.length };
    }
  },

  /**
   * Search/filter avatars with server-side pagination.
   */
  searchAvatars: async (params: SearchParams): Promise<{ avatars: Avatar[]; total: number; has_more: boolean }> => {
    const qs = new URLSearchParams();
    if (params.search) qs.set('search', params.search);
    if (params.collection) qs.set('collection', params.collection);
    if (params.license) qs.set('license', params.license);
    qs.set('limit', String(params.limit || 60));
    qs.set('offset', String(params.offset || 0));

    try {
      const res = await fetch(`${API_BASE}/avatars?${qs}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: APIAvatarResponse = await res.json();
      return {
        avatars: data.avatars.map(mapApiAvatar),
        total: data.total,
        has_more: data.has_more || false,
      };
    } catch (err) {
      reportApiFailure('api.search', `/avatars?${qs}`, err);
      const all = getAvatars() as Avatar[];
      let filtered = all;
      if (params.search) {
        const q = params.search.toLowerCase();
        filtered = filtered.filter(a => a.name.toLowerCase().includes(q) || a.collection.toLowerCase().includes(q));
      }
      if (params.collection) {
        filtered = filtered.filter(a => a.collection === params.collection);
      }
      const offset = params.offset || 0;
      const limit = params.limit || 60;
      return {
        avatars: filtered.slice(offset, offset + limit),
        total: filtered.length,
        has_more: offset + limit < filtered.length,
      };
    }
  },

  /**
   * Raw API collections response (slug, name, avatar_count, license).
   * Used by sidebar filters.
   */
  getApiCollections: async (): Promise<{ slug: string; name: string; avatar_count: number; license?: string }[]> => {
    try {
      const res = await fetch(`${API_BASE}/collections`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: APICollectionsResponse = await res.json();
      return data.collections;
    } catch (err) {
      reportApiFailure('api.collections', '/collections', err);
      return [];
    }
  },

  /**
   * Fetch avatars for a specific collection with server-side pagination.
   * This is the primary method for collection detail pages.
   */
  getCollectionAvatars: async (
    collectionSlug: string,
    params?: { limit?: number; offset?: number; search?: string }
  ): Promise<{ avatars: Avatar[]; total: number; has_more: boolean }> => {
    const qs = new URLSearchParams();
    qs.set('collection', collectionSlug);
    if (params?.search) qs.set('search', params.search);
    qs.set('limit', String(params?.limit || 60));
    qs.set('offset', String(params?.offset || 0));

    try {
      const res = await fetch(`${API_BASE}/avatars?${qs}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: APIAvatarResponse = await res.json();
      return {
        avatars: data.avatars.map(mapApiAvatar),
        total: data.total,
        has_more: data.has_more || false,
      };
    } catch (err) {
      reportApiFailure('api.collection_avatars', `/avatars?${qs}`, err);
      const all = getAvatars() as Avatar[];
      let filtered = all.filter(a =>
        a.collection.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') === collectionSlug
      );
      if (params?.search) {
        const q = params.search.toLowerCase();
        filtered = filtered.filter(a => a.name.toLowerCase().includes(q) || a.id.toString().includes(q));
      }
      const offset = params?.offset || 0;
      const limit = params?.limit || 60;
      return {
        avatars: filtered.slice(offset, offset + limit),
        total: filtered.length,
        has_more: offset + limit < filtered.length,
      };
    }
  },
};
