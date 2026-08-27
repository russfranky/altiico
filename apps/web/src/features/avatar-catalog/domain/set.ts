import type { AvatarSetReadiness, AvatarSetState, AvatarVerificationStatus, EvidenceProvenance } from './common';

export type AvatarSetSummary = Readonly<{
  id: string;
  slug: string;
  displayName: string;
  archiveCode: string;
  description: string;
  state: AvatarSetState;
  readiness: AvatarSetReadiness;
  avatarCountLabel: string;
  imageSrc: string;
  imageAlt: string;
  tags: readonly string[];
  provenance: EvidenceProvenance;
}>;

export type AvatarSetSourceIdentity = Readonly<{
  sourceSystem: string;
  sourceCollectionId: string;
  chain: string | null;
  contractAddress: string | null;
}>;

export type AvatarSetEvidenceSummary = Readonly<{
  provenance: EvidenceProvenance;
  verificationStatus: AvatarVerificationStatus;
  validationScopeLabel: string;
  licenseLabel: string;
  licenseReviewRequired: boolean;
  freshnessLabel: string;
  warningLabels: readonly string[];
}>;

export type AvatarSlotSummary = Readonly<{
  slotId: string;
  productAvatarId: string;
  avatarSlug: string;
  displayLabel: string;
  sourceAssetId: string | null;
  apiAvatarId: string | null;
  tokenId: string | null;
  imageSrc: string;
  imageAlt: string;
  formatLabel: string;
  readiness: AvatarSetReadiness;
  verificationStatus: AvatarVerificationStatus;
}>;

export type AvatarSetDetail = AvatarSetSummary & Readonly<{
  longDescription: string;
  identity: AvatarSetSourceIdentity;
  evidence: AvatarSetEvidenceSummary;
  avatarSlots: readonly AvatarSlotSummary[];
}>;
