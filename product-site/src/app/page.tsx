import Link from 'next/link';
import { BentoPanel, ProductShell } from '@/components/product-shell';
import { RobotAnchor } from '@/components/robot-anchor';

export default function Home() {
  return (
    <ProductShell section="AVATAR FACTORY / ONLINE">
      <div className="bentoGrid landingGrid">
        <BentoPanel className="heroCell">
          <span className="eyebrow">PUBLIC AVATAR IDENTITY SYSTEM</span>
          <h1>YOUR ALTER EGO<br />STARTS HERE.</h1>
          <p>Discover avatar identities, see the evidence behind them, and carry a stable identity into Hubzz.</p>
          <Link className="systemButton primary" href="/explore/avatar-sets">BROWSE AVATAR SETS <span>→</span></Link>
        </BentoPanel>

        <BentoPanel className="robotCell">
          <RobotAnchor />
        </BentoPanel>

        <BentoPanel className="homeSupportCell">
          <div className="supportStatement">
            <span className="eyebrow">DISCOVER</span>
            <h2>Find the identity first.</h2>
            <p>Browse product-owned sets and individual avatars before entering the engine.</p>
          </div>
          <div className="supportStatement">
            <span className="eyebrow">VERIFY</span>
            <h2>Keep the evidence attached.</h2>
            <p>Source, validation, and license claims stay visible without becoming the public identity.</p>
          </div>
        </BentoPanel>
      </div>
    </ProductShell>
  );
}
