import { SystemLabel } from '@altiico/ui';
import type { AvatarSetEvidenceSummary } from '../../domain';
import { displayProvenance } from '../../presentation/format-provenance';

export function SetEvidencePanel({ evidence }: { evidence: AvatarSetEvidenceSummary }) {
  return (
    <div className="setDetailPanel setEvidencePanel">
      <SystemLabel tone="signal">EVIDENCE / READINESS</SystemLabel>
      <h2>CLAIMS FOLLOW EVIDENCE.</h2>
      <dl className="setEvidenceReadout">
        <div><dt>EVIDENCE SOURCE</dt><dd>{displayProvenance(evidence.provenance)}</dd></div>
        <div><dt>VERIFICATION</dt><dd>{evidence.verificationStatus}</dd></div>
        <div><dt>VALIDATION</dt><dd>{evidence.validationScopeLabel}</dd></div>
        <div><dt>LICENSE</dt><dd>{evidence.licenseLabel}</dd></div>
        <div><dt>FRESHNESS</dt><dd>{evidence.freshnessLabel}</dd></div>
        <div><dt>LICENSE REVIEW</dt><dd>{evidence.licenseReviewRequired ? 'REQUIRED' : 'CLEAR'}</dd></div>
      </dl>
      <div className="setWarningList" aria-label="Set warnings">
        {evidence.warningLabels.map((warning) => <span key={warning}>{warning}</span>)}
      </div>
    </div>
  );
}
