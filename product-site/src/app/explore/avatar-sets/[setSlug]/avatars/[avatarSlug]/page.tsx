import Link from 'next/link';
import { notFound } from 'next/navigation';
import { BentoPanel, ProductShell } from '@/components/product-shell';
import { RobotAnchor } from '@/components/robot-anchor';
import { localCatalogAdapter } from '@/lib/catalog';

type Params = Promise<{ setSlug: string; avatarSlug: string }>;

export default async function AvatarPage({ params }: { params: Params }) {
  const { setSlug, avatarSlug } = await params;
  const set = await localCatalogAdapter.getSetBySlug(setSlug);
  const avatar = await localCatalogAdapter.getAvatarBySlug(setSlug, avatarSlug);
  if (!set || !avatar) notFound();
  return (
    <ProductShell section="ENTITY / PROFILE">
      <div className="bentoGrid avatarGrid">
        <BentoPanel className="avatarTitle" label="ENTITY / PRODUCT IDENTITY"><Link className="backLink" href={`/explore/avatar-sets/${set.slug}`}>← {set.name}</Link><h1>{avatar.name}</h1><code>{avatar.id}</code></BentoPanel>
        <BentoPanel className="avatarVisual" label={avatar.role === 'primary' ? 'PRIMARY ENTITY' : 'SUPPORTING ENTITY'}><RobotAnchor /></BentoPanel>
        <BentoPanel className="avatarEvidence" label="EVIDENCE"><div className="metricRow"><span>STATE</span><b>{avatar.evidence.state}</b></div><div className="metricRow"><span>SOURCE ID</span><b>{avatar.sourceAssetId ?? 'NOT MAPPED'}</b></div><div className="metricRow"><span>TOKEN ID</span><b>{avatar.tokenId ?? 'NOT MAPPED'}</b></div><div className="metricRow"><span>VRM SPEC</span><b>{avatar.vrmSpec ?? 'PENDING'}</b></div></BentoPanel>
        <BentoPanel className="avatarTraits" label="TRAITS">{avatar.traits.map((trait) => <div className="traitRow" key={`${trait.label}-${trait.value}`}><span>{trait.label}</span><b>{trait.value}</b><em>{trait.source}</em></div>)}</BentoPanel>
        <BentoPanel className="previewCell" label="3D PREVIEW / RESERVED"><h2>ENGINE VIEW</h2><p>The WebGL viewer enters here after the visual shell and adapter contracts pass review.</p><button disabled>OPEN STUDIO →</button></BentoPanel>
      </div>
    </ProductShell>
  );
}
