import { SignalStatus, SystemIcon, SystemLabel, TechnicalFrame } from '@altiico/ui';

export function HomeOperationsSection() {
  return (
    <section id="operations" className="narrativeSection narrativeSection--operations" aria-labelledby="operations-title">
      <div className="narrativeIndex"><SystemLabel tone="signal">03 / OPERATIONS</SystemLabel><SystemIcon name="cube" /></div>
      <div className="narrativeCopy">
        <SystemLabel tone="muted">INTERNAL ASSET SURFACE</SystemLabel>
        <h2 id="operations-title">ONE CONTROL SURFACE FROM INTAKE TO RELEASE.</h2>
        <p className="narrativeLead">Altiico keeps avatar-set operations next to the visual checks that inform them. The same system can stage sets, review readiness, manage emotes, and prepare releases.</p>
        <p className="narrativeNote">Public discovery stays separate from privileged operations. The brand remains one system, while permissions and responsibilities remain clear.</p>
      </div>
      <TechnicalFrame className="operationsPanel">
        <div className="operationsPanelHeader"><SystemLabel tone="muted">ASSET PIPELINE / STATIC MODEL</SystemLabel><SignalStatus label="MODEL / READY" /></div>
        <div className="operationsRows"><div><span>SET INTAKE</span><strong>01</strong><em>QUEUED</em></div><div><span>ASSET PREP</span><strong>02</strong><em>STAGED</em></div><div><span>VISUAL QA</span><strong>03</strong><em>VERIFY</em></div><div><span>RELEASE</span><strong>04</strong><em>PUBLISH</em></div></div>
      </TechnicalFrame>
    </section>
  );
}
