import Link from 'next/link';
import { notFound } from 'next/navigation';
import { BentoPanel, ProductShell } from '@/components/product-shell';
import { RobotAnchor } from '@/components/robot-anchor';
import { localCatalogAdapter } from '@/lib/catalog';

export async function generateMetadata({ params }: { params: Promise<{ setSlug: string }> }) {
  const { setSlug } = await params;
  const set = await localCatalogAdapter.getSetBySlug(setSlug);
  return { title: set ? set.name : 'Avatar set' };
}

export default async function AvatarSetPage({ params }: { params: Promise<{ setSlug: string }> }) {
  const { setSlug } = await params;
  const set = await localCatalogAdapter.getSetBySlug(setSlug);
  if (!set) notFound();

  return (
    <ProductShell section="SET / DETAIL">
      <div className="bentoGrid detailGrid">
        <BentoPanel className="detailIdentity">
          <Link className="backLink" href="/explore/avatar-sets">← ALL SETS</Link>
          <span className="eyebrow">AVATAR SET</span>
          <h1>{set.name}</h1>
          <p>{set.description}</p>
          <div className="identityStrip" aria-label="Set identity and evidence">
            <span><small>CHAIN</small><b>{set.chain ?? '—'}</b></span>
            <span><small>CONTRACT</small><b>{set.contract ?? 'NOT SET'}</b></span>
            <span><small>EVIDENCE</small><b>{set.evidence.state}</b></span>
            <span><small>LICENSE</small><b>{set.license ?? 'REVIEW'}</b></span>
          </div>
          <code>{set.id}</code>
        </BentoPanel>

        <BentoPanel className="detailVisual">
          <RobotAnchor />
        </BentoPanel>

        <BentoPanel className="membersCell">
          <div className="sectionHeading">
            <div>
              <span className="eyebrow">AVATAR MEMBERS</span>
              <h2>Choose an identity.</h2>
            </div>
            <span className="memberCount">{set.avatars.length} MEMBERS</span>
          </div>
          <div className="memberGrid">
            {set.avatars.length ? set.avatars.map((avatar) => (
              <Link
                key={avatar.id}
                className={`memberCard ${avatar.role === 'primary' ? 'memberPrimary' : ''}`}
                href={`/explore/avatar-sets/${set.slug}/avatars/${avatar.slug}`}
              >
                <span>{avatar.role}</span>
                <strong>{avatar.name}</strong>
                <em>{avatar.evidence.state}</em>
              </Link>
            )) : <p>No product avatar members are defined in this fixture.</p>}
          </div>
        </BentoPanel>
      </div>
    </ProductShell>
  );
}
