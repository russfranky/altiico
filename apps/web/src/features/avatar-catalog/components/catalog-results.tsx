import { SystemLabel } from '@altiico/ui';
import type { AvatarSetSummary, EvidenceProvenance } from '../domain';
import { displayProvenance } from '../presentation/format-provenance';
import { AvatarSetCard } from './avatar-set-card';

export function CatalogResults({ items, provenance }: { items: readonly AvatarSetSummary[]; provenance: EvidenceProvenance }) {
  return (
    <section className="catalogResults">
      <div className="catalogResultsHeader">
        <SystemLabel tone="muted" aria-live="polite">VISIBLE SETS / {String(items.length).padStart(2, '0')}</SystemLabel>
        <SystemLabel tone="muted">SOURCE / {displayProvenance(provenance).toUpperCase()}</SystemLabel>
      </div>
      {items.length ? (
        <div className="catalogGrid">{items.map((item) => <AvatarSetCard key={item.id} item={item} />)}</div>
      ) : (
        <div className="catalogEmpty">
          <SystemLabel tone="signal">NO MATCH / 00</SystemLabel>
          <h2>NO SETS MATCH THIS FILTER.</h2>
          <p>Reset the filters or change the search term. The empty state is explicit and does not change source data.</p>
        </div>
      )}
    </section>
  );
}
