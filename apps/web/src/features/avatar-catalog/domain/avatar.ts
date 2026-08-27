import type { AvatarSetReadiness, AvatarVerificationStatus, EvidenceProvenance } from './common';
import type { AvatarSetSummary } from './set';

export type AvatarProductIdentity = Readonly<{
  productAvatarId: string;
  avatarSlug: string;
  productSetId: string;
  setSlug: string;
  sourceAssetId: string | null;
  apiAvatarId: string | null;
  tokenId: string | null;
  chain: string | null;
  contractAddress: string | null;
}>;

export type AvatarAssetEvidence = Readonly<{
  provenance: EvidenceProvenance;
  verificationStatus: AvatarVerificationStatus;
  validationScopeLabel: string;
  sourceUri: string | null;
  transportUri: string | null;
  sourceCheckStatus: string | null;
  reachable: boolean | null;
  vrmSpec: string | null;
  fileSizeBytes: number | null;
  checkedAtLabel: string;
  warningLabels: readonly string[];
}>;

export type AvatarTrait = Readonly<{
  key: string;
  value: string;
  provenance: EvidenceProvenance;
}>;

export type AvatarPreviewState = Readonly<{
  mode: 'reserved' | 'available';
  label: string;
  note: string;
}>;

export type AvatarDetail = Readonly<{
  productAvatarId: string;
  avatarSlug: string;
  displayName: string;
  archiveCode: string;
  description: string;
  imageSrc: string;
  imageAlt: string;
  formatLabel: string;
  readiness: AvatarSetReadiness;
  provenance: EvidenceProvenance;
  set: AvatarSetSummary;
  identity: AvatarProductIdentity;
  evidence: AvatarAssetEvidence;
  traits: readonly AvatarTrait[];
  preview: AvatarPreviewState;
}>;
