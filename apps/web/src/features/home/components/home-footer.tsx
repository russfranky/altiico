import { BrandMark, SignalStatus, SystemLabel } from '@altiico/ui';

export function HomeFooter() {
  return (
    <footer className="siteFooter">
      <div className="siteFooterBrand"><BrandMark /><p>The avatar identity and asset system for Hubzz.</p></div>
      <nav className="siteFooterNav" aria-label="Footer navigation">
        <div><SystemLabel tone="signal">SYSTEM</SystemLabel><a href="/explore/avatar-sets">Discovery</a><a href="#verification">Verification</a><a href="#operations">Operations</a></div>
        <div><SystemLabel tone="signal">BUILD</SystemLabel><a href="#systems">Modules</a><a href="#identity">Identity model</a><a href="#top">Return to top</a></div>
      </nav>
      <div className="siteFooterReadout"><SignalStatus /><SystemLabel tone="muted">ALTIICO / IN-WORLD SINCE 07.4</SystemLabel><SystemLabel tone="muted">FOUNDATION / T-004</SystemLabel></div>
    </footer>
  );
}
