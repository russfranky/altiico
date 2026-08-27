import type { EvidenceProvenance } from '../../domain';

export function legacySnapshotProvenance(snapshotId: string): EvidenceProvenance {
  return {
    sourceId: 'legacy-altiico',
    sourceMode: 'snapshot',
    snapshotId,
  };
}
