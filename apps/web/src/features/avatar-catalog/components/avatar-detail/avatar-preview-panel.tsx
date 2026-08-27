import { SystemLabel, TechnicalFrame } from '@altiico/ui';
import type { AvatarPreviewState } from '../../domain';

export function AvatarPreviewPanel({ preview }: { preview: AvatarPreviewState }) {
  return (
    <div className="avatarDetailPanel avatarPreviewPanel">
      <SystemLabel tone="signal">PREVIEW / ENTRY POINT</SystemLabel>
      <h2>THE PROFILE OWNS THE DOOR. STUDIO OWNS THE ENGINE.</h2>
      <TechnicalFrame className="avatarPreviewFrame">
        <div className="avatarPreviewTarget" aria-hidden="true">+</div>
        <SystemLabel tone="signal">{preview.label}</SystemLabel>
        <p>{preview.note}</p>
        <SystemLabel tone="muted">STUDIO WEBGL / NOT CONNECTED</SystemLabel>
      </TechnicalFrame>
    </div>
  );
}
