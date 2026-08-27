export type AvatarSetState = 'published' | 'staged' | 'review';
export type AvatarSetReadiness = 'ready' | 'review' | 'blocked';
export type AvatarVerificationStatus = 'verified' | 'partial' | 'unverified';

export type EvidenceProvenance = Readonly<{
  sourceId: string;
  sourceMode: 'fixture' | 'service' | 'snapshot';
  snapshotId: string | null;
}>;
