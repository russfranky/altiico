import Image from 'next/image';
import { SystemButton, SystemLabel, TechnicalFrame } from '@altiico/ui';
import type { AvatarSetSummary } from '../domain';
import { avatarSetRoute } from '../routes';
import { displayProvenance } from '../presentation/format-provenance';

export function AvatarSetCard({ item }: { item: AvatarSetSummary }) {
  return (
    <TechnicalFrame className="catalogCard">
      <div className="catalogCardMedia">
        <Image src={item.imageSrc} alt={item.imageAlt} fill sizes="(max-width: 620px) 100vw, (max-width: 1000px) 50vw, 28vw" />
      </div>
      <div className="catalogCardBody">
        <div className="catalogCardTopline">
          <SystemLabel tone="signal">{item.archiveCode}</SystemLabel>
          <SystemLabel tone="muted">{displayProvenance(item.provenance).toUpperCase()}</SystemLabel>
        </div>
        <h2>{item.displayName}</h2>
        <p>{item.description}</p>
        <dl className="catalogCardReadout">
          <div><dt>STATE</dt><dd>{item.state}</dd></div>
          <div><dt>READINESS</dt><dd>{item.readiness}</dd></div>
          <div><dt>GROUP</dt><dd>{item.avatarCountLabel}</dd></div>
        </dl>
        <div className="catalogCardTags">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
        <SystemButton className="catalogCardAction" variant="secondary" href={avatarSetRoute(item.slug)}>INSPECT SET</SystemButton>
      </div>
    </TechnicalFrame>
  );
}
