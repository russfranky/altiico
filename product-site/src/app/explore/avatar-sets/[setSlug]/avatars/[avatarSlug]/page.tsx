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
        <BentoPanel className="avatarTitle">
          <Link className="backLink" href={`/explore/avatar-sets/${set.slug}`}>← {set.name}</Link>
          <span className="eyebrow">{avatar.role === 'primary' ? 'PRIMARY AVATAR' : 'AVATAR PROFILE'}</span>
          <h1>{avatar.name}</h1>
          <p>A stable public identity with evidence kept separate from route ownership.</p>
          <code>{avatar.id}</code>
        </BentoPanel>

        <BentoPanel className="avatarVisual">
          <RobotAnchor />
        </BentoPanel>

        <BentoPanel className="avatarDetails">
          <div className="identityStrip" aria-label="Avatar evidence summary">
            <span><small>STATE</small><b>{avatar.evidence.state}</b></span>
            <span><small>SOURCE ID</small><b>{avatar.sourceAssetId ?? 'NOT MAPPED'}</b></span>
            <span><small>TOKEN ID</small><b>{avatar.tokenId ?? 'NOT MAPPED'}</b></span>
            <span><small>VRM SPEC</small><b>{avatar.vrmSpec ?? 'PENDING'}</b></span>
          </div>

          {avatar.traits.length ? (
            <div className="traitList" aria-label="Avatar traits">
              {avatar.traits.map((trait) => (
                <div className="traitRow" key={`${trait.label}-${trait.value}`}>
                  <span>{trait.label}</span>
                  <b>{trait.value}</b>
                  <em>{trait.source}</em>
                </div>
              ))}
            </div>
          ) : null}

          <p className="studioNote">3D engine preview stays out of this page until the viewer is real and useful.</p>
        </BentoPanel>
      </div>
    </ProductShell>
  );
}
