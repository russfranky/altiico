import Image from 'next/image';
import { SystemButton, SystemLabel, TechnicalFrame } from '@altiico/ui';
import type { AvatarSetDetail } from '../../domain';
import { avatarSetRoute } from '../../routes';
import { displayProvenance } from '../../presentation/format-provenance';

export function SetHero({ item }: { item: AvatarSetDetail }) {
  return (
    <section className="setDetailHero" aria-labelledby="set-title">
      <div className="setDetailHeroCopy">
        <SystemButton variant="quiet" href="/explore/avatar-sets">BACK TO AVATAR SETS</SystemButton>
        <SystemLabel tone="signal">{item.archiveCode} / SET DETAIL</SystemLabel>
        <h1 id="set-title">{item.displayName}</h1>
        <p>{item.longDescription}</p>
        <div className="setDetailHeroStatus">
          <span>{item.state}</span><span>{item.readiness}</span><span>{displayProvenance(item.provenance)}</span>
        </div>
      </div>
      <div className="setDetailHeroVisual">
        <TechnicalFrame className="setHeroFrame">
          <div className="setHeroImage">
            <Image src={item.imageSrc} alt={item.imageAlt} fill priority sizes="(max-width: 820px) 90vw, 44vw" />
            <SystemLabel className="setHeroArchive" tone="signal">{item.archiveCode}</SystemLabel>
          </div>
          <div className="setHeroFooter">
            <SystemLabel tone="muted">ROUTE / {avatarSetRoute(item.slug).toUpperCase()}</SystemLabel>
            <SystemLabel tone="muted">DATA / {displayProvenance(item.provenance).toUpperCase()}</SystemLabel>
          </div>
        </TechnicalFrame>
      </div>
    </section>
  );
}
