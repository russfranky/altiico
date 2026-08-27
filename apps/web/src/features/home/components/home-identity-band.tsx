import { SystemLabel } from '@altiico/ui';

export function HomeIdentityBand() {
  return (
    <section id="identity" className="identityBand" aria-labelledby="identity-title">
      <div className="identityBandLabel"><SystemLabel tone="signal">IDENTITY MODEL / 07.4</SystemLabel></div>
      <div className="identityBandCopy"><h2 id="identity-title">IDENTITY → ASSET → PRESENCE</h2><p>Altiico connects avatar identity, public discovery, engine-true verification, and asset operations as one coherent system.</p></div>
      <dl className="identityReadout"><div><dt>01</dt><dd>DISCOVER</dd></div><div><dt>02</dt><dd>VERIFY</dd></div><div><dt>03</dt><dd>OPERATE</dd></div></dl>
    </section>
  );
}
