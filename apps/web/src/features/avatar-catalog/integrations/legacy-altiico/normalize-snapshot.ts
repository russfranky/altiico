import type {
  LegacyAltiicoSnapshot,
  LegacyAltiicoSourceAvatarSnapshot,
  LegacyAltiicoStagingSet,
} from './contracts';

export type LegacyAltiicoSnapshotInput = {
  staging: LegacyAltiicoSnapshot;
  sourceAvatarsBySetSlug: Record<string, LegacyAltiicoSourceAvatarSnapshot | undefined>;
};

export type LegacyAltiicoConvergenceIssue = {
  code: 'snapshot_id_mismatch' | 'set_slug_mismatch' | 'orphan_source_snapshot';
  setSlug: string;
  detail: string;
};

export type NormalizedLegacyAltiicoSet = {
  stagingSet: LegacyAltiicoStagingSet;
  sourceAvatarSnapshot: LegacyAltiicoSourceAvatarSnapshot | null;
};

export type NormalizedLegacyAltiicoSnapshot = {
  sourceSystem: 'legacy-altiico';
  snapshotId: string;
  generatedAt: string;
  sets: NormalizedLegacyAltiicoSet[];
  issues: LegacyAltiicoConvergenceIssue[];
};

export function normalizeLegacyAltiicoSnapshot(input: LegacyAltiicoSnapshotInput): NormalizedLegacyAltiicoSnapshot {
  const issues: LegacyAltiicoConvergenceIssue[] = [];
  const stagingSlugs = new Set(input.staging.sets.map((item) => item.set.slug));
  const sets = input.staging.sets.map((stagingSet) => {
    const sourceAvatarSnapshot = input.sourceAvatarsBySetSlug[stagingSet.set.slug] ?? null;
    if (sourceAvatarSnapshot?.snapshotId !== undefined && sourceAvatarSnapshot.snapshotId !== input.staging.snapshotId) {
      issues.push({
        code: 'snapshot_id_mismatch',
        setSlug: stagingSet.set.slug,
        detail: `staging=${input.staging.snapshotId}; source=${sourceAvatarSnapshot.snapshotId}`,
      });
    }
    if (sourceAvatarSnapshot && sourceAvatarSnapshot.setSlug !== stagingSet.set.slug) {
      issues.push({
        code: 'set_slug_mismatch',
        setSlug: stagingSet.set.slug,
        detail: `staging=${stagingSet.set.slug}; source=${sourceAvatarSnapshot.setSlug}`,
      });
    }
    return { stagingSet, sourceAvatarSnapshot };
  });

  for (const [setSlug, snapshot] of Object.entries(input.sourceAvatarsBySetSlug)) {
    if (snapshot && !stagingSlugs.has(setSlug)) {
      issues.push({ code: 'orphan_source_snapshot', setSlug, detail: `source snapshot has no staging set for ${setSlug}` });
    }
  }

  return {
    sourceSystem: 'legacy-altiico',
    snapshotId: input.staging.snapshotId,
    generatedAt: input.staging.generatedAt,
    sets,
    issues,
  };
}
