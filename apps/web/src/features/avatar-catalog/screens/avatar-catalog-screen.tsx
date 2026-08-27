import { SystemLabel } from '@altiico/ui';
import type { AvatarSetSummary, EvidenceProvenance } from '../domain';
import { displayProvenance } from '../presentation/format-provenance';
import { AvatarCatalogExplorer } from '../components/avatar-catalog-explorer';

export function AvatarCatalogScreen({ items, provenance }: { items: readonly AvatarSetSummary[]; provenance: EvidenceProvenance }) {
  return (
    <>
      <section className="catalogHero">
        <div>
          <SystemLabel tone="signal">EXPLORE / AVATAR SETS</SystemLabel>
          <h1>THE LINEUP.</h1>
          <p>Browse Altiico avatar sets through a source-neutral catalog port. The source can change without changing this screen.</p>
        </div>
        <dl>
          <div><dt>SOURCE</dt><dd>{displayProvenance(provenance).toUpperCase()}</dd></div>
          <div><dt>ROUTE</dt><dd>/EXPLORE/AVATAR-SETS</dd></div>
          <div><dt>BOUNDARY</dt><dd>CATALOG PORT</dd></div>
        </dl>
      </section>
      <div id="catalog-content"><AvatarCatalogExplorer initialItems={items} provenance={provenance} /></div>
      <footer className="pageFooter">
        <SystemLabel tone="muted">PUBLIC DISCOVERY / ROUTE 01</SystemLabel>
        <SystemLabel tone="muted">FOUNDATION / SOURCE-NEUTRAL</SystemLabel>
      </footer>
    </>
  );
}
