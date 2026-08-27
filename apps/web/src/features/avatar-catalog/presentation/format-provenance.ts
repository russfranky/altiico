import type { EvidenceProvenance } from '../domain';

export function displayProvenance(provenance: EvidenceProvenance): string {
  return provenance.snapshotId ? `${provenance.sourceId} / ${provenance.snapshotId}` : provenance.sourceId;
}

export function describeProvenance(provenance: EvidenceProvenance): string {
  if (provenance.sourceMode === 'fixture') return 'Fixture data proves the interface contract without making live catalog claims.';
  if (provenance.sourceMode === 'snapshot') return 'Snapshot data is read-only evidence from a deterministic source artifact.';
  return 'Service data is supplied through the catalog port.';
}
