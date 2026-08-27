import Image from 'next/image';
import { SystemButton, SystemIcon, SystemLabel, TechnicalFrame } from '@altiico/ui';

export function HomeDiscoverySection() {
  return (
    <section id="discovery" className="narrativeSection narrativeSection--discovery" aria-labelledby="discovery-title">
      <div className="narrativeIndex"><SystemLabel tone="signal">01 / DISCOVERY</SystemLabel><SystemIcon name="ii" /></div>
      <div className="narrativeCopy">
        <SystemLabel tone="muted">PUBLIC IDENTITY SURFACE</SystemLabel>
        <h2 id="discovery-title">FIND THE IDENTITY BEFORE YOU ENTER THE WORLD.</h2>
        <p className="narrativeLead">Altiico gives avatar sets a public home. People can understand the set, inspect its characters, and choose how they want to appear in Hubzz.</p>
        <div className="narrativeFacts"><div><span>01</span><p>Browse by avatar set and individual character.</p></div><div><span>02</span><p>Keep source identity, imagery, and provenance visible.</p></div><div><span>03</span><p>Use 3D preview when the character itself needs inspection.</p></div></div>
        <SystemButton variant="primary" href="/explore/avatar-sets">OPEN AVATAR SETS</SystemButton>
      </div>
      <div className="discoveryVisual">
        <TechnicalFrame className="identityCard identityCard--face"><Image src="/brand/entity-face.png" alt="Close portrait of an Altiico entity" fill sizes="(max-width: 820px) 70vw, 24vw" /><span>ENTITY / FACE</span></TechnicalFrame>
        <TechnicalFrame className="identityCard identityCard--detail"><Image src="/brand/entity-detail.png" alt="Detailed view of an Altiico entity" fill sizes="(max-width: 820px) 70vw, 24vw" /><span>ENTITY / DETAIL</span></TechnicalFrame>
      </div>
    </section>
  );
}
