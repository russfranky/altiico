import type { AvatarSetReadiness, AvatarSetState, EvidenceProvenance } from './common';
import type { AvatarSetSummary } from './set';

export type AvatarCatalogQuery = Readonly<{
  search?: string;
  state?: AvatarSetState | 'all';
  readiness?: AvatarSetReadiness | 'all';
}>;

export type AvatarCatalogResult = Readonly<{
  items: readonly AvatarSetSummary[];
  provenance: EvidenceProvenance;
}>;
