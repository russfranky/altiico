import type { AvatarDetail, AvatarVerificationStatus } from '../../domain';
import type { LegacyAltiicoSourceAvatar, LegacyAltiicoStagingSet } from './contracts';
import { legacySnapshotProvenance } from './provenance';

function verificationStatusForAvatar(item: LegacyAltiicoSourceAvatar): AvatarVerificationStatus {
  if (item.vrmValidated) return 'verified';
  if (item.reachable) return 'partial';
  return 'unverified';
}

function warningLabels(item: LegacyAltiicoSourceAvatar) {
  const warnings: string[] = [];
  if (!item.reachable) warnings.push('source_unreachable');
  if (!item.vrmValidated) warnings.push('vrm_not_binary_validated');
  return warnings;
}

export function augmentAvatarWithLegacyEvidence(
  product: AvatarDetail,
  parentSet: LegacyAltiicoStagingSet,
  source: LegacyAltiicoSourceAvatar,
  generatedAt: string,
  snapshotId: string,
): AvatarDetail {
  return {
    ...product,
    identity: {
      ...product.identity,
      sourceAssetId: product.identity.sourceAssetId ?? source.id,
      tokenId: product.identity.tokenId ?? source.tokenId,
      chain: product.identity.chain ?? parentSet.set.chain,
      contractAddress: product.identity.contractAddress ?? parentSet.set.contract,
    },
    evidence: {
      provenance: legacySnapshotProvenance(snapshotId),
      verificationStatus: verificationStatusForAvatar(source),
      validationScopeLabel: source.validationScope || parentSet.sourceAssets.validationScope || 'UNKNOWN',
      sourceUri: source.originalSourceUrl,
      transportUri: null,
      sourceCheckStatus: source.checkStatus,
      reachable: source.reachable,
      vrmSpec: source.vrmSpec,
      fileSizeBytes: source.fileSizeOriginal,
      checkedAtLabel: source.checkedAt ?? generatedAt,
      warningLabels: warningLabels(source),
    },
  };
}
