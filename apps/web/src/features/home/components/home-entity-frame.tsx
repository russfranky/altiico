import Image from 'next/image';
import { SignalStatus, SystemLabel, TechnicalFrame } from '@altiico/ui';

export function HomeEntityFrame() {
  return (
    <TechnicalFrame className="entityFrame">
      <div className="entityViewport">
        <Image className="entityPortrait" src="/brand/entity-full.png" width={438} height={410} priority alt="Hooded Altiico entity portrait" />
        <span className="entityVerticalId" aria-hidden="true">ALT_07.4</span>
      </div>
      <div className="entityReadout">
        <SystemLabel tone="muted">ENTITY / 07.4</SystemLabel>
        <SignalStatus label="STATUS: ONLINE" />
      </div>
    </TechnicalFrame>
  );
}
