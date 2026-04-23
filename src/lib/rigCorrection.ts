/**
 * RigCorrection types and serialization helpers.
 *
 * Every drag offset captured in altiico is stored as a RigCorrectionEntry.
 * A session accumulates entries; Export serializes the whole list.
 */

export interface RigCorrectionOffset {
  x: number;
  y: number;
  z: number;
}

export type RigCorrectionScope = 'avatar' | 'collection';

export interface RigCorrectionEntry {
  scope: RigCorrectionScope;
  /** Always present. For scope='avatar', identifies the specific avatar. For 'collection', identifies which one it applies to. */
  collectionSlug: string;
  /** Only present when scope='avatar'. */
  avatarId?: string;
  /** Display name — avatar name for 'avatar' scope, collection name for 'collection' scope. */
  displayName: string;
  animationId: string | null;
  seatHeight: 'none' | 'floor' | 'chair' | 'stool';
  facingDeg: number;
  offset: RigCorrectionOffset;
  timestamp: string;
  altiicoVersion: string;
}

export interface RigCorrectionSession {
  exportedAt: string;
  altiicoVersion: string;
  entryCount: number;
  entries: RigCorrectionEntry[];
}

const ALTIICO_VERSION = '0.1.0';

export function makeEntry(params: {
  scope: RigCorrectionScope;
  collectionSlug: string;
  avatarId?: string;
  displayName: string;
  animationId: string | null;
  seatHeight: 'none' | 'floor' | 'chair' | 'stool';
  facingDeg: number;
  offset: RigCorrectionOffset;
}): RigCorrectionEntry {
  return {
    ...params,
    timestamp: new Date().toISOString(),
    altiicoVersion: ALTIICO_VERSION,
  };
}

/**
 * Cascade resolution: given a set of entries and an (avatarId, collectionSlug),
 * returns the effective offset for that avatar in-world.
 *
 * Order: default (0,0,0) → latest collection entry for this collection → latest avatar entry for this avatar.
 * Last write wins within each scope layer.
 */
export function resolveEffectiveOffset(
  entries: RigCorrectionEntry[],
  avatarId: string,
  collectionSlug: string,
): {
  offset: RigCorrectionOffset;
  source: 'default' | 'collection' | 'avatar';
  collectionEntry: RigCorrectionEntry | null;
  avatarEntry: RigCorrectionEntry | null;
} {
  let collectionEntry: RigCorrectionEntry | null = null;
  let avatarEntry: RigCorrectionEntry | null = null;

  for (const e of entries) {
    if (e.scope === 'collection' && e.collectionSlug === collectionSlug) {
      collectionEntry = e;
    } else if (e.scope === 'avatar' && e.avatarId === avatarId) {
      avatarEntry = e;
    }
  }

  if (avatarEntry) return { offset: avatarEntry.offset, source: 'avatar', collectionEntry, avatarEntry };
  if (collectionEntry) return { offset: collectionEntry.offset, source: 'collection', collectionEntry, avatarEntry };
  return { offset: { x: 0, y: 0, z: 0 }, source: 'default', collectionEntry, avatarEntry };
}

export function exportSession(entries: RigCorrectionEntry[]): void {
  const session: RigCorrectionSession = {
    exportedAt: new Date().toISOString(),
    altiicoVersion: ALTIICO_VERSION,
    entryCount: entries.length,
    entries,
  };

  const json = JSON.stringify(session, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const date = new Date().toISOString().slice(0, 10);
  const a = document.createElement('a');
  a.href = url;
  a.download = `rig-corrections-${date}.json`;
  a.click();

  // Release immediately — browser has enqueued the download
  URL.revokeObjectURL(url);
}
