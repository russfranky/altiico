import Image from 'next/image';
import { SystemIcon, SystemLabel, TechnicalFrame } from '@altiico/ui';

export function HomeVerificationSection() {
  return (
    <section id="verification" className="narrativeSection narrativeSection--verification" aria-labelledby="verification-title">
      <div className="narrativeIndex"><SystemLabel tone="signal">02 / VERIFICATION</SystemLabel><SystemIcon name="crosshair" /></div>
      <div className="verificationVisual">
        <TechnicalFrame className="verificationFrame">
          <div className="verificationViewport"><Image src="/brand/entity-shoulder.png" alt="Altiico entity shown inside a technical verification frame" width={360} height={410} /><span className="verificationAxis verificationAxis--x" aria-hidden="true" /><span className="verificationAxis verificationAxis--y" aria-hidden="true" /><span className="verificationCross" aria-hidden="true">+</span></div>
          <div className="verificationReadout"><SystemLabel tone="muted">VIEW / ISOMETRIC</SystemLabel><SystemLabel tone="signal">ENGINE PARITY</SystemLabel></div>
        </TechnicalFrame>
      </div>
      <div className="narrativeCopy">
        <SystemLabel tone="muted">ENGINE-TRUE QA SURFACE</SystemLabel>
        <h2 id="verification-title">WHAT YOU SEE HERE MUST MATCH WHAT YOU SEE IN HUBZZ.</h2>
        <p className="narrativeLead">The Studio is the controlled place to inspect scale, rig behavior, animation, framing, and imagery before an avatar reaches the world.</p>
        <dl className="technicalReadout"><div><dt>CAMERA</dt><dd>ORTHOGRAPHIC</dd></div><div><dt>ORIENTATION</dt><dd>CANONICAL ISOMETRIC</dd></div><div><dt>CHECKS</dt><dd>RIG / SCALE / MOTION</dd></div><div><dt>RULE</dt><dd>HUBZZ IS VISUAL TRUTH</dd></div></dl>
      </div>
    </section>
  );
}
