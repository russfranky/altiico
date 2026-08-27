import { SystemLabel } from '@altiico/ui';
import { homeFlowStages } from '../content';

export function HomeFlowSection() {
  return (
    <section className="flowSection" aria-labelledby="flow-title">
      <div className="sectionHeading"><div><SystemLabel tone="signal">SYSTEM FLOW / 04 STAGES</SystemLabel><h2 id="flow-title">FROM ASSET TO PRESENCE.</h2></div><p>Altiico does not replace the identity inside the asset. It gives that identity a clear path into Hubzz.</p></div>
      <ol className="flowGrid">{homeFlowStages.map((stage) => <li key={stage.index}><SystemLabel tone="signal">{stage.index}</SystemLabel><h3>{stage.title}</h3><p>{stage.copy}</p></li>)}</ol>
    </section>
  );
}
