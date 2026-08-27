import Link from 'next/link';
import { BentoPanel, ProductShell } from '@/components/product-shell';
import { RobotAnchor } from '@/components/robot-anchor';

export default function Home() {
  return (
    <ProductShell section="AVATAR FACTORY / ONLINE">
      <div className="bentoGrid landingGrid">
        <BentoPanel className="heroCell" label="ALTIICO / HUBZZ IDENTITY INFRASTRUCTURE">
          <h1>YOUR ALTER EGO<br />STARTS HERE.</h1>
          <p>One public system for avatar identity, discovery, verification, and evidence-aware operations.</p>
          <Link className="systemButton primary" href="/explore/avatar-sets">BROWSE AVATAR SETS <span>→</span></Link>
        </BentoPanel>
        <BentoPanel className="robotCell" label="ENTITY / PRIMARY"><RobotAnchor /></BentoPanel>
        <BentoPanel className="smallCell" label="01 / DISCOVER"><h2>BROWSE THE LINEUP.</h2><p>Find a set before you enter the world.</p></BentoPanel>
        <BentoPanel className="smallCell" label="02 / VERIFY"><h2>SEE ENGINE TRUTH.</h2><p>Keep visual claims tied to evidence.</p></BentoPanel>
        <BentoPanel className="wideCell" label="03 / OPERATE"><div className="metricRow"><span>IDENTITY</span><b>PRODUCT OWNED</b></div><div className="metricRow"><span>EVIDENCE</span><b>ADAPTER FED</b></div><div className="metricRow"><span>PUBLICATION</span><b>REVIEW GATED</b></div></BentoPanel>
      </div>
    </ProductShell>
  );
}
