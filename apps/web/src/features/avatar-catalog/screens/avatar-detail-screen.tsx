import { SystemLabel } from '@altiico/ui';
import type { AvatarDetail, AvatarSetDetail } from '../domain';
import { selectAvatarSiblings } from '../queries/avatar-siblings';
import { AvatarEvidencePanel } from '../components/avatar-detail/avatar-evidence-panel';
import { AvatarHero } from '../components/avatar-detail/avatar-hero';
import { AvatarIdentityPanel } from '../components/avatar-detail/avatar-identity-panel';
import { AvatarPreviewPanel } from '../components/avatar-detail/avatar-preview-panel';
import { AvatarSiblingNav } from '../components/avatar-detail/avatar-sibling-nav';
import { AvatarTraitsPanel } from '../components/avatar-detail/avatar-traits-panel';

export function AvatarDetailScreen({ item, set }: { item: AvatarDetail; set: AvatarSetDetail }) {
  const siblings = selectAvatarSiblings(set.avatarSlots, item.avatarSlug);
  return (
    <>
      <AvatarHero item={item} set={set} />
      <section className="avatarDetailGrid" aria-label="Avatar product identity and source evidence">
        <AvatarIdentityPanel identity={item.identity} />
        <AvatarEvidencePanel evidence={item.evidence} />
      </section>
      <section className="avatarDetailGrid avatarDetailGrid--lower" aria-label="Avatar traits and preview">
        <AvatarTraitsPanel traits={item.traits} />
        <AvatarPreviewPanel preview={item.preview} />
      </section>
      <AvatarSiblingNav set={set} previous={siblings.previous} next={siblings.next} />
      <footer className="pageFooter">
        <SystemLabel tone="muted">PUBLIC DISCOVERY / AVATAR DETAIL</SystemLabel>
        <SystemLabel tone="muted">FOUNDATION / T-006</SystemLabel>
      </footer>
    </>
  );
}
