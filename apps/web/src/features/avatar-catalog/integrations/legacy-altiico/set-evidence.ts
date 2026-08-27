import type { AvatarSetDetail, AvatarSetEvidenceSummary, AvatarSetSourceIdentity, AvatarVerificationStatus } from '../../domain';
import type { LegacyAltiicoStagingSet } from './contracts';
import { legacySnapshotProvenance } from './provenance';

function verificationStatusForSet(item: LegacyAltiicoStagingSet): AvatarVerificationStatus {
  if (item.sourceAssets.count > 0 && item.sourceAssets.binaryValidatedCount === item.sourceAssets.count) return 'verified';
  if (item.sourceAssets.binaryValidatedCount > 0) return 'partial';
  return 'unverified';
}

export function mapLegacySetSourceIdentity(item: LegacyAltiicoStagingSet): AvatarSetSourceIdentity {
  return {
    sourceSystem: 'legacy-altiico',
    sourceCollectionId: item.set.slug,
    chain: item.set.chain,
    contractAddress: item.set.contract,
  };
}

export function mapLegacySetEvidence(item: LegacyAltiicoStagingSet, generatedAt: string, snapshotId: string): AvatarSetEvidenceSummary {
  return {
    provenance: legacySnapshotProvenance(snapshotId),
    verificationStatus: verificationStatusForSet(item),
    validationScopeLabel: item.sourceAssets.validationScope || 'UNKNOWN',
    licenseLabel: item.set.license ?? 'LICENSE UNKNOWN',
    licenseReviewRequired: item.warnings.includes('license_requires_review') || item.set.license === null,
    freshnessLabel: item.sampleEvidence?.validatedAt ?? generatedAt,
    warningLabels: [...item.warnings],
  };
}

export function augmentSetWithLegacyEvidence(
  product: AvatarSetDetail,
  legacy: LegacyAltiicoStagingSet,
  generatedAt: string,
  snapshotId: string,
): AvatarSetDetail {
  const sourceIdentity = mapLegacySetSourceIdentity(legacy);
  return {
    ...product,
    identity: {
      ...product.identity,
      chain: product.identity.chain ?? sourceIdentity.chain,
      contractAddress: product.identity.contractAddress ?? sourceIdentity.contractAddress,
    },
    evidence: mapLegacySetEvidence(legacy, generatedAt, snapshotId),
  };
}
