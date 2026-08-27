import Link from 'next/link';
import { notFound } from 'next/navigation';
import { BentoPanel, ProductShell } from '@/components/product-shell';
import { RobotAnchor } from '@/components/robot-anchor';
import { localCatalogAdapter } from '@/lib/catalog';

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; const set = await localCatalogAdapter.getSetBySlug(slug);
  return { title: set ? set.name : 'Avatar set' };
}

export default async function AvatarSetPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; const set = await localCatalogAdapter.getSetBySlug(slug); if (!set) notFound();
  return (
    <ProductShell section="SET / DETAIL">
      <div className="bentoGrid detailGrid">
        <BentoPanel className="detailIdentity" label="SET / PRODUCT IDENTITY"><Link className="backLink" href="/explore/avatar-sets">← ALL SETS</Link><h1>{set.name}</h1><p>{set.description}</p><code>{set.id}</code></BentoPanel>
        <BentoPanel className="detailVisual" label="PRIMARY ENTITY"><RobotAnchor /></BentoPanel>
        <BentoPanel className="identityFacts" label="SOURCE IDENTITY"><div className="metricRow"><span>SLUG</span><b>{set.slug}</b></div><div className="metricRow"><span>CHAIN</span><b>{set.chain ?? '—'}</b></div><div className="metricRow"><span>CONTRACT</span><b>{set.contract ?? 'NOT SET'}</b></div></BentoPanel>
        <BentoPanel className="evidenceFacts" label="EVIDENCE"><div className="metricRow"><span>STATE</span><b>{set.evidence.state}</b></div><div className="metricRow"><span>SOURCE</span><b>{set.evidence.source}</b></div><div className="metricRow"><span>LICENSE</span><b>{set.license ?? 'REVIEW'}</b></div></BentoPanel>
        <BentoPanel className="membersCell" label="AVATAR MEMBERS"><div className="memberGrid">{set.avatars.length ? set.avatars.map((avatar) => <Link key={avatar.id} className={`memberCard ${avatar.role === 'primary' ? 'memberPrimary' : ''}`} href={`/explore/avatar-sets/${set.slug}/avatars/${avatar.slug}`}><span>{avatar.role}</span><strong>{avatar.name}</strong><em>{avatar.evidence.state}</em></Link>) : <p>No product avatar members are defined in this fixture.</p>}</div></BentoPanel>
      </div>
    </ProductShell>
  );
}
