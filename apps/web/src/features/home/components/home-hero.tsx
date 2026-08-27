import { SystemButton, SystemLabel } from '@altiico/ui';
import { HomeEntityFrame } from './home-entity-frame';

export function HomeHero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="heroCopy">
        <SystemLabel tone="muted">ALTIICO / HUBZZ IDENTITY INFRASTRUCTURE</SystemLabel>
        <h1 id="hero-title">YOUR ALTER<br />EGO STARTS<br />HERE.</h1>
        <div className="heroIntro"><p>THE AVATAR IDENTITY AND ASSET SYSTEM FOR HUBZZ.</p><p>DISCOVER. VERIFY. OPERATE.</p></div>
        <div className="heroActions">
          <SystemButton variant="primary" href="/explore/avatar-sets">BROWSE AVATAR SETS</SystemButton>
          <SystemButton variant="secondary" href="#verification">SEE ENGINE TRUTH</SystemButton>
        </div>
      </div>
      <div className="heroVisual"><HomeEntityFrame /></div>
    </section>
  );
}
