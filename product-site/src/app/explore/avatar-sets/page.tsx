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
        <BentoPanel className="catalogIntro">
          <span className="eyebrow">EXPLORE / AVATAR SETS</span>
          <h1>THE LINEUP.</h1>
          <p>Browse stable product identities first. Evidence stays attached, but never becomes the public ID.</p>
          <div className="evidenceStrip" aria-label="Pinned catalog evidence summary">
            <span><small>PASSING</small><b>{catalogEvidence.summary.passing}</b></span>
            <span><small>FAILING</small><b>{catalogEvidence.summary.failing}</b></span>
            <span><small>TOTAL</small><b>{catalogEvidence.summary.collections}</b></span>
            <code>{catalogEvidence.source.path} @ {catalogEvidence.source.commit.slice(0, 8)}</code>
          </div>
        </BentoPanel>

        {sets.map((set, index) => (
          <BentoPanel key={set.id} className={`setCell ${index === 0 ? 'setCellPrimary' : ''}`}>
            <div className="setCardTop">
              <span className={`status status-${set.evidence.state}`}>{set.evidence.state}</span>
              <span>{set.readiness}</span>
            </div>
            <h2>{set.name}</h2>
            <p>{set.description}</p>
            <div className="setFacts">
              <span>AVATARS <b>{set.avatars.length}</b></span>
              <span>CHAIN <b>{set.chain ?? '—'}</b></span>
            </div>
            <Link className="systemButton" href={`/explore/avatar-sets/${set.slug}`}>OPEN SET <span>→</span></Link>
          </BentoPanel>
        ))}
      </div>
    </ProductShell>
  );
}
