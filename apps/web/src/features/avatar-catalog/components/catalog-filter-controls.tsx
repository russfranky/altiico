import { SystemLabel } from '@altiico/ui';
import type { AvatarSetReadiness, AvatarSetState, EvidenceProvenance } from '../domain';
import { describeProvenance, displayProvenance } from '../presentation/format-provenance';

export type CatalogFilterState = AvatarSetState | 'all';
export type CatalogFilterReadiness = AvatarSetReadiness | 'all';

export function CatalogFilterControls({
  provenance,
  search,
  state,
  readiness,
  onSearchChange,
  onStateChange,
  onReadinessChange,
  onReset,
}: {
  provenance: EvidenceProvenance;
  search: string;
  state: CatalogFilterState;
  readiness: CatalogFilterReadiness;
  onSearchChange(value: string): void;
  onStateChange(value: CatalogFilterState): void;
  onReadinessChange(value: CatalogFilterReadiness): void;
  onReset(): void;
}) {
  return (
    <aside className="catalogFilters" aria-label="Avatar set filters">
      <div className="catalogFilterHeader"><SystemLabel tone="signal">FILTER / CURRENT INDEX</SystemLabel><button type="button" onClick={onReset}>RESET</button></div>
      <label><span>SEARCH</span><input value={search} onChange={(event) => onSearchChange(event.target.value)} placeholder="SET / TAG / ARCHIVE" /></label>
      <label><span>STATE</span><select value={state} onChange={(event) => onStateChange(event.target.value as CatalogFilterState)}><option value="all">ALL</option><option value="published">PUBLISHED</option><option value="staged">STAGED</option><option value="review">REVIEW</option></select></label>
      <label><span>READINESS</span><select value={readiness} onChange={(event) => onReadinessChange(event.target.value as CatalogFilterReadiness)}><option value="all">ALL</option><option value="ready">READY</option><option value="review">REVIEW</option><option value="blocked">BLOCKED</option></select></label>
      <div className="catalogFixtureNote"><SystemLabel tone="muted">DATA / {displayProvenance(provenance).toUpperCase()}</SystemLabel><p>{describeProvenance(provenance)}</p></div>
    </aside>
  );
}
