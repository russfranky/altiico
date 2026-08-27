import type { EvidenceProvenance } from '../../../domain';

export const fixtureLicenseLabel = 'NO LICENSE CLAIM / LOCAL FIXTURE';
export const fixtureFreshnessLabel = 'LOCAL / STATIC';
export const fixtureProvenance: EvidenceProvenance = {
  sourceId: 'local-fixture',
  sourceMode: 'fixture',
  snapshotId: null,
};
