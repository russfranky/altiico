import Link from 'next/link';
import { BentoPanel, ProductShell } from '@/components/product-shell';
import { localCatalogAdapter } from '@/lib/catalog';

export const metadata = { title: 'Avatar Sets' };

export default async function AvatarSetsPage() {
  const [sets, catalogEvidence] = await Promise.all([
    localCatalogAdapter.listSets(),
    localCatalogAdapter.getCatalogEvidenceSnapshot(),
  ]);

  return (
    <ProductShell section="EXPLORE / PINNED EVIDENCE">
      <div className="bentoGrid catalogGrid">
        <BentoPanel className="catalogIntro" label="EXPLORE / AVATAR SETS">
          <h1>THE LINEUP.</h1><p>Browse product-owned set identities. Evidence remains visible without becoming the public ID.</p>
        </BentoPanel>
        <BentoPanel className="filterCell" label="FILTER / FOUNDATION">
          <div className="filterReadout"><span>QUERY</span><b>ALL SETS</b></div><div className="filterReadout"><span>STATE</span><b>ANY</b></div><div className="filterReadout"><span>SOURCE</span><b>FIXTURE + PINNED QA</b></div>
        </BentoPanel>
        {sets.map((set, index) => (
          <BentoPanel key={set.id} className={`setCell ${index === 0 ? 'setCellPrimary' : ''}`} label={`${String(index + 1).padStart(2, '0')} / SET`}>
            <div className="setCardTop"><span className={`status status-${set.evidence.state}`}>{set.evidence.state}</span><span>{set.readiness}</span></div>
            <h2>{set.name}</h2><p>{set.description}</p>
            <div className="setFacts"><span>AVATARS <b>{set.avatars.length}</b></span><span>CHAIN <b>{set.chain ?? '—'}</b></span></div>
            <Link className="systemButton" href={`/explore/avatar-sets/${set.slug}`}>OPEN SET <span>→</span></Link>
          </BentoPanel>
        ))}
        <BentoPanel className="evidenceCell" label="PINNED CATALOG EVIDENCE">
          <p>Root catalog acceptance is connected through the adapter. No catalog identity maps to a product ID yet.</p>
          <div className="setFacts">
            <span>PASSING <b>{catalogEvidence.summary.passing}</b></span>
            <span>FAILING <b>{catalogEvidence.summary.failing}</b></span>
            <span>TOTAL <b>{catalogEvidence.summary.collections}</b></span>
          </div>
          <p><code>{catalogEvidence.source.path} @ {catalogEvidence.source.commit.slice(0, 8)}</code></p>
        </BentoPanel>
      </div>
    </ProductShell>
  );
}
