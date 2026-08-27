import { SystemLabel } from '@altiico/ui';
import type { AvatarAssetEvidence } from '../../domain';
import { displayBytes, displayOptional, displayReachability } from '../../presentation/format';
import { displayProvenance } from '../../presentation/format-provenance';

export function AvatarEvidencePanel({ evidence }: { evidence: AvatarAssetEvidence }) {
  return (
    <div className="avatarDetailPanel avatarEvidencePanel">
      <SystemLabel tone="signal">SOURCE / EVIDENCE</SystemLabel>
      <h2>THE SOURCE CAN ADD FACTS WITHOUT OWNING THE PAGE.</h2>
      <dl className="avatarEvidenceReadout">
        <div><dt>EVIDENCE SOURCE</dt><dd>{displayProvenance(evidence.provenance)}</dd></div>
        <div><dt>VERIFY</dt><dd>{evidence.verificationStatus}</dd></div>
        <div><dt>VALIDATION</dt><dd>{evidence.validationScopeLabel}</dd></div>
        <div><dt>REACHABILITY</dt><dd>{displayReachability(evidence.reachable)}</dd></div>
        <div><dt>VRM SPEC</dt><dd>{displayOptional(evidence.vrmSpec)}</dd></div>
        <div><dt>FILE SIZE</dt><dd>{displayBytes(evidence.fileSizeBytes)}</dd></div>
        <div><dt>CHECK STATUS</dt><dd>{displayOptional(evidence.sourceCheckStatus)}</dd></div>
        <div><dt>CHECKED</dt><dd>{evidence.checkedAtLabel}</dd></div>
        <div><dt>SOURCE URI</dt><dd className="avatarLongValue">{displayOptional(evidence.sourceUri)}</dd></div>
      </dl>
      <div className="avatarWarningList" aria-label="Avatar evidence warnings">
        {evidence.warningLabels.map((warning) => <span key={warning}>{warning}</span>)}
      </div>
    </div>
  );
}
