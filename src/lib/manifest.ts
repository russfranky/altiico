/**
 * Collection manifest — the unified artifact altiico produces for hubzz to consume.
 *
 * One file per collection. Merges avatar-api metadata (identity, assets) with
 * altiico's rig corrections (session-collected, cascade pre-resolved).
 *
 * The hubzz engine reads this at avatar-load time:
 *   1. fetches `/files/collections/<slug>/manifest.json` (one-time, cached)
 *   2. finds the avatar's entry by id
 *   3. if rigCorrection present, applies offset on top of snapToTilePosition
 *
 * Cascade resolution happens here at export — the consumer doesn't resolve anything.
 * source: 'avatar' means per-avatar override present; 'collection' means inherits
 * collection default; 'default' means no correction (field omitted in output).
 */
import type { ApiAvatar, ApiCollection } from './avatarApiTypes';
import { getVrmUrl } from './avatarApiTypes';
import type { RigCorrectionEntry, RigCorrectionOffset } from './rigCorrection';
import { resolveEffectiveOffset } from './rigCorrection';

const ALTIICO_VERSION = '0.1.0';
const MANIFEST_SCHEMA_VERSION = '1.0';

export interface ManifestRigCorrection {
  offset: RigCorrectionOffset;
  /** 'avatar' = override, 'collection' = inherits default. 'default' entries are omitted. */
  source: 'avatar' | 'collection';
}

export interface ManifestAvatar {
  id: string;
  tokenId: string | null;
  name: string;
  vrmUrl: string | null;
  pfpThumbnailUrl: string;
  fbThumbnailUrl: string | null;
  contract: string | null;
  chain: string;
  license: string;
  contentRating: string | null;
  rigCorrection?: ManifestRigCorrection;
}

export interface CollectionManifest {
  schemaVersion: string;
  altiicoVersion: string;
  collectionSlug: string;
  collectionName: string;
  exportedAt: string;
  avatarCount: number;
  defaultRigCorrection?: ManifestRigCorrection;
  avatars: ManifestAvatar[];
}

/** Build the manifest ID in the format used by session entries: `<slug>:<tokenId>`. */
function makeAvatarId(avatar: ApiAvatar): string {
  return `${avatar.collection_slug}:${avatar.id}`;
}

const ASSET_BASE = 'https://altii.co';

function conventionalPfpThumbUrl(avatar: ApiAvatar): string {
  return `${ASSET_BASE}/thumbs/${avatar.collection_slug}/${avatar.id}-pfp.png`;
}

function conventionalFbThumbUrl(avatar: ApiAvatar): string {
  return `${ASSET_BASE}/thumbs/${avatar.collection_slug}/${avatar.id}-fb.png`;
}

/**
 * Build one CollectionManifest from avatar-api data + session entries.
 *
 * Caller supplies the collection + its avatars (from avatar-api cache).
 * Entries can be the full session — this function filters to the ones relevant
 * to the given collection.
 */
export function buildCollectionManifest(
  collection: ApiCollection,
  avatars: ApiAvatar[],
  allSessionEntries: RigCorrectionEntry[],
): CollectionManifest {
  // Find the latest collection-scope entry for this collection
  const collectionEntries = allSessionEntries.filter(
    (e) => e.scope === 'collection' && e.collectionSlug === collection.slug,
  );
  const latestCollectionEntry = collectionEntries[collectionEntries.length - 1] ?? null;

  const defaultRigCorrection: ManifestRigCorrection | undefined = latestCollectionEntry
    ? { offset: latestCollectionEntry.offset, source: 'collection' }
    : undefined;

  const manifestAvatars: ManifestAvatar[] = avatars.map((avatar) => {
    const avatarId = makeAvatarId(avatar);
    const resolution = resolveEffectiveOffset(
      allSessionEntries,
      avatarId,
      collection.slug,
    );

    let rigCorrection: ManifestRigCorrection | undefined;
    if (resolution.source === 'avatar' && resolution.avatarEntry) {
      rigCorrection = { offset: resolution.avatarEntry.offset, source: 'avatar' };
    }
    // 'collection' source inherits defaultRigCorrection at the top of the manifest;
    // we don't duplicate it per-avatar. 'default' means no correction — field omitted.

    return {
      id: avatarId,
      tokenId: avatar.token_id ?? null,
      name: avatar.name,
      vrmUrl: getVrmUrl(avatar),
      pfpThumbnailUrl: conventionalPfpThumbUrl(avatar),
      fbThumbnailUrl: conventionalFbThumbUrl(avatar),
      contract: avatar.contract,
      chain: avatar.chain,
      license: avatar.license || avatar.collection_license,
      contentRating: avatar.contentRating,
      ...(rigCorrection ? { rigCorrection } : {}),
    };
  });

  return {
    schemaVersion: MANIFEST_SCHEMA_VERSION,
    altiicoVersion: ALTIICO_VERSION,
    collectionSlug: collection.slug,
    collectionName: collection.name,
    exportedAt: new Date().toISOString(),
    avatarCount: manifestAvatars.length,
    ...(defaultRigCorrection ? { defaultRigCorrection } : {}),
    avatars: manifestAvatars,
  };
}

/** Download one CollectionManifest as a JSON file. */
export function downloadManifest(manifest: CollectionManifest): void {
  const json = JSON.stringify(manifest, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const date = new Date().toISOString().slice(0, 10);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${manifest.collectionSlug}-manifest-${date}.json`;
  a.click();

  URL.revokeObjectURL(url);
}

/**
 * Returns the unique set of collection slugs touched by any session entry.
 * Used to know which manifests to emit on bulk export.
 */
export function collectionsTouchedBySession(entries: RigCorrectionEntry[]): string[] {
  const slugs = new Set<string>();
  for (const e of entries) slugs.add(e.collectionSlug);
  return Array.from(slugs);
}
