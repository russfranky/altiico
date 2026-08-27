import { SystemLabel } from '@altiico/ui';
import type { AvatarTrait } from '../../domain';
import { displayProvenance } from '../../presentation/format-provenance';

export function AvatarTraitsPanel({ traits }: { traits: readonly AvatarTrait[] }) {
  return (
    <div className="avatarDetailPanel">
      <SystemLabel tone="signal">TRAITS / OBSERVED VALUES</SystemLabel>
      <h2>TRAITS NEED THEIR OWN PROVENANCE.</h2>
      <div className="avatarTraitList">
        {traits.map((trait) => (
          <div key={`${trait.key}-${trait.value}`}>
            <SystemLabel tone="muted">{trait.key}</SystemLabel>
            <strong>{trait.value}</strong>
            <SystemLabel tone="muted">{displayProvenance(trait.provenance)}</SystemLabel>
          </div>
        ))}
      </div>
    </div>
  );
}
