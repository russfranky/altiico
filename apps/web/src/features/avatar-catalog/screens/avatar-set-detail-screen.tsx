import { SystemLabel } from '@altiico/ui';
import type { AvatarSetDetail } from '../domain';
import { SetAvatarSection } from '../components/set-detail/set-avatar-section';
import { SetEvidencePanel } from '../components/set-detail/set-evidence-panel';
import { SetHero } from '../components/set-detail/set-hero';
import { SetIdentityPanel } from '../components/set-detail/set-identity-panel';


export function AvatarSetDetailScreen({ item }: { item: AvatarSetDetail }) {
  return (
    <>
      <SetHero item={item} />
      <section className="setDetailGrid" aria-label="Set identity and evidence">
        <SetIdentityPanel item={item} />
        <SetEvidencePanel evidence={item.evidence} />
      </section>
      <SetAvatarSection item={item} />
      <footer className="pageFooter">
        <SystemLabel tone="muted">PUBLIC DISCOVERY / SET DETAIL</SystemLabel>
        <SystemLabel tone="muted">FOUNDATION / T-006</SystemLabel>
      </footer>
    </>
  );
}
