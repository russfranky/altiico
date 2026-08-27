import { SystemLabel } from '@altiico/ui';
import type { AvatarSetDetail } from '../../domain';
import { AvatarSlotGrid } from './avatar-slot-grid';

export function SetAvatarSection({ item }: { item: AvatarSetDetail }) {
  return (
    <section className="setAvatarSection" aria-labelledby="avatar-slots-title">
      <div className="setAvatarHeading">
        <div>
          <SystemLabel tone="signal">AVATAR SLOTS / {String(item.avatarSlots.length).padStart(2, '0')}</SystemLabel>
          <h2 id="avatar-slots-title">THE SET HAS MEMBERS. EACH ONE KEEPS ITS OWN IDENTITY.</h2>
        </div>
        <p>Product avatar slugs stay separate from source asset IDs and token IDs.</p>
      </div>
      <AvatarSlotGrid setSlug={item.slug} slots={item.avatarSlots} />
    </section>
  );
}
