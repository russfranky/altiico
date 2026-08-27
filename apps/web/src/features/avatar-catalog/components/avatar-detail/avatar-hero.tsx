import Image from 'next/image';
import { SystemButton, SystemLabel, TechnicalFrame } from '@altiico/ui';
import type { AvatarDetail, AvatarSetSummary } from '../../domain';
import { avatarSetRoute } from '../../routes';
import { displayProvenance } from '../../presentation/format-provenance';

export function AvatarHero({ item, set }: { item: AvatarDetail; set: AvatarSetSummary }) {
  return (
    <section className="avatarDetailHero" aria-labelledby="avatar-title">
      <div className="avatarDetailHeroCopy">
        <div className="avatarDetailBacklinks">
          <SystemButton variant="quiet" href={avatarSetRoute(set.slug)}>BACK TO {set.displayName}</SystemButton>
          <SystemLabel tone="muted">SET / {set.archiveCode}</SystemLabel>
        </div>
        <SystemLabel tone="signal">{item.archiveCode} / AVATAR DETAIL</SystemLabel>
        <h1 id="avatar-title">{item.displayName}</h1>
        <p>{item.description}</p>
        <div className="avatarDetailStatus">
          <span>{item.readiness}</span><span>{item.evidence.verificationStatus}</span><span>{displayProvenance(item.provenance)}</span>
        </div>
      </div>
      <div className="avatarDetailHeroVisual">
        <TechnicalFrame className="avatarHeroFrame">
          <div className="avatarHeroImage">
            <Image src={item.imageSrc} alt={item.imageAlt} fill priority sizes="(max-width: 820px) 92vw, 44vw" />
            <SystemLabel className="avatarHeroArchive" tone="signal">{item.archiveCode}</SystemLabel>
          </div>
          <div className="avatarHeroFooter">
            <SystemLabel tone="muted">FORMAT / {item.formatLabel}</SystemLabel>
            <SystemLabel tone="muted">DATA / {displayProvenance(item.provenance).toUpperCase()}</SystemLabel>
          </div>
        </TechnicalFrame>
      </div>
    </section>
  );
}
