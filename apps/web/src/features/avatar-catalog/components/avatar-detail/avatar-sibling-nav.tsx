import { SystemButton, SystemLabel } from '@altiico/ui';
import type { AvatarSetSummary, AvatarSlotSummary } from '../../domain';
import { avatarDetailRoute, avatarSetRoute } from '../../routes';

export function AvatarSiblingNav({
  set,
  previous,
  next,
}: {
  set: AvatarSetSummary;
  previous: AvatarSlotSummary | null;
  next: AvatarSlotSummary | null;
}) {
  return (
    <nav className="avatarSiblingNav" aria-label="Avatar set member navigation">
      <div>
        <SystemLabel tone="muted">PREVIOUS MEMBER</SystemLabel>
        {previous ? <SystemButton variant="secondary" href={avatarDetailRoute(set.slug, previous.avatarSlug)}>{previous.displayLabel}</SystemButton> : <span className="avatarSiblingEmpty">START OF SET</span>}
      </div>
      <div className="avatarSiblingSet">
        <SystemLabel tone="muted">PARENT SET</SystemLabel>
        <SystemButton variant="quiet" href={avatarSetRoute(set.slug)}>{set.displayName}</SystemButton>
      </div>
      <div>
        <SystemLabel tone="muted">NEXT MEMBER</SystemLabel>
        {next ? <SystemButton variant="secondary" href={avatarDetailRoute(set.slug, next.avatarSlug)}>{next.displayLabel}</SystemButton> : <span className="avatarSiblingEmpty">END OF SET</span>}
      </div>
    </nav>
  );
}
