'use client';

import { useMemo, useState } from 'react';
import type { AvatarSetSummary, EvidenceProvenance } from '../domain';
import { filterAvatarSets } from '../queries/filter-avatar-sets';
import { CatalogFilterControls, type CatalogFilterReadiness, type CatalogFilterState } from './catalog-filter-controls';
import { CatalogResults } from './catalog-results';

export function AvatarCatalogExplorer({ initialItems, provenance }: { initialItems: readonly AvatarSetSummary[]; provenance: EvidenceProvenance }) {
  const [search, setSearch] = useState('');
  const [state, setState] = useState<CatalogFilterState>('all');
  const [readiness, setReadiness] = useState<CatalogFilterReadiness>('all');
  const visible = useMemo(
    () => filterAvatarSets(initialItems, { search, state, readiness }),
    [initialItems, readiness, search, state],
  );

  function reset() {
    setSearch('');
    setState('all');
    setReadiness('all');
  }

  return (
    <div className="catalogExplorer">
      <CatalogFilterControls
        provenance={provenance}
        search={search}
        state={state}
        readiness={readiness}
        onSearchChange={setSearch}
        onStateChange={setState}
        onReadinessChange={setReadiness}
        onReset={reset}
      />
      <CatalogResults items={visible} provenance={provenance} />
    </div>
  );
}
