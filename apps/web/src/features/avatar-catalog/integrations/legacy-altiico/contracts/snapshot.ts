import type { LegacyAltiicoSourceAvatar } from './avatar';
import type { LegacyAltiicoStagingSet } from './set';

export type LegacyAltiicoSnapshot = {
  schema: 'hubzz-prealpha-staging-v1' | string;
  schemaVersion: number;
  generatedAt: string;
  snapshotId: string;
  sets: LegacyAltiicoStagingSet[];
};

export type LegacyAltiicoSourceAvatarSnapshot = {
  schema: 'hubzz-prealpha-source-avatars-v1' | string;
  schemaVersion: number;
  generatedAt: string;
  snapshotId: string;
  setSlug: string;
  count: number;
  reachableCount: number;
  binaryValidatedCount: number;
  avatars: LegacyAltiicoSourceAvatar[];
};
