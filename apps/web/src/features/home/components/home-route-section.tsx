import { SystemLabel } from '@altiico/ui';
import { homeRouteBoundaries } from '../content';

export function HomeRouteSection() {
  return (
    <section className="routeSection" aria-labelledby="route-title">
      <div className="routeSectionCopy"><SystemLabel tone="signal">ROUTE BOUNDARIES / FOUNDATION</SystemLabel><h2 id="route-title">ONE BRAND. CLEAR SURFACES.</h2><p>The homepage establishes the shared system. Each product surface gets its own route and responsibility.</p></div>
      <div className="routeTable" role="list">{homeRouteBoundaries.map((item) => <div key={item.route} className="routeRow" role="listitem"><code>{item.route}</code><span>{item.surface}</span><SystemLabel tone={item.state.startsWith('LIVE') ? 'signal' : 'muted'}>{item.state}</SystemLabel></div>)}</div>
    </section>
  );
}
