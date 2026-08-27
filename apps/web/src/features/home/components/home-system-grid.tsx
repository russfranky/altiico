import { homeSystemModules } from '../content';
import { HomeSystemModule } from './home-system-module';

export function HomeSystemGrid() {
  return (
    <section id="systems" className="systemGrid" aria-label="Altiico system modules">
      {homeSystemModules.map((item) => <HomeSystemModule key={item.index} {...item} />)}
    </section>
  );
}
