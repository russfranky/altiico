import { SystemLabel } from '@altiico/ui';
import type { AvatarSetDetail } from '../../domain';
import { displayOptional } from '../../presentation/format';

export function SetIdentityPanel({ item }: { item: AvatarSetDetail }) {
  return (
    <div className="setDetailPanel">
      <SystemLabel tone="signal">IDENTITY / CANONICAL FIELDS</SystemLabel>
      <h2>KEEP IDENTITIES SEPARATE.</h2>
      <p>Set, chain, contract, source, and avatar identities remain distinct fields.</p>
      <dl className="setIdentityReadout">
        <div><dt>SOURCE</dt><dd>{item.identity.sourceSystem}</dd></div>
        <div><dt>SOURCE ID</dt><dd>{item.identity.sourceCollectionId}</dd></div>
        <div><dt>CHAIN</dt><dd>{displayOptional(item.identity.chain)}</dd></div>
        <div><dt>CONTRACT</dt><dd className="setMonospaceValue">{displayOptional(item.identity.contractAddress)}</dd></div>
      </dl>
    </div>
  );
}
