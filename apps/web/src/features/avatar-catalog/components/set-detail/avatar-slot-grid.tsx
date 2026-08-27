import Image from 'next/image';
import { SystemButton, SystemLabel, TechnicalFrame } from '@altiico/ui';
import type { AvatarSlotSummary } from '../../domain';
import { displayOptional } from '../../presentation/format';
import { avatarDetailRoute } from '../../routes';

export function AvatarSlotGrid({ setSlug, slots }: { setSlug: string; slots: readonly AvatarSlotSummary[] }) {
  return (
    <div className="avatarSlotGrid">
      {slots.map((slot, index) => (
        <TechnicalFrame className="avatarSlotCard" key={slot.slotId}>
          <div className="avatarSlotMedia">
            <Image src={slot.imageSrc} alt={slot.imageAlt} fill sizes="(max-width: 620px) 100vw, (max-width: 1000px) 50vw, 24vw" />
            <SystemLabel className="avatarSlotIndex" tone="signal">{String(index + 1).padStart(2, '0')}</SystemLabel>
          </div>
          <div className="avatarSlotBody">
            <h3>{slot.displayLabel}</h3>
            <dl>
              <div><dt>FORMAT</dt><dd>{slot.formatLabel}</dd></div>
              <div><dt>READINESS</dt><dd>{slot.readiness}</dd></div>
              <div><dt>VERIFY</dt><dd>{slot.verificationStatus}</dd></div>
              <div><dt>TOKEN ID</dt><dd>{displayOptional(slot.tokenId)}</dd></div>
            </dl>
            <SystemButton className="avatarSlotAction" variant="secondary" href={avatarDetailRoute(setSlug, slot.avatarSlug)}>OPEN AVATAR</SystemButton>
          </div>
        </TechnicalFrame>
      ))}
    </div>
  );
}
