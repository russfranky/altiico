import { BrandMark, SignalStatus, SystemLabel } from '@altiico/ui';
import { MobileNav } from '@/components/mobile-nav';

const navItems = [
  { href: '/#systems', label: 'System' },
  { href: '/explore/avatar-sets', label: 'Explore' },
  { href: '/#verification', label: 'Studio' },
  { href: '/#operations', label: 'Pipeline' },
];

export function SiteHeader() {
  return (
    <header className="siteHeader">
      <a className="siteHeaderBrand" href="/" aria-label="Altiico home"><BrandMark /></a>
      <nav className="siteNav" aria-label="Primary navigation">
        {navItems.map((item) => (
          <a key={item.label} href={item.href} className="siteNavLink"><SystemLabel tone="muted">{item.label}</SystemLabel></a>
        ))}
      </nav>
      <div className="siteHeaderStatus"><SignalStatus /></div>
      <MobileNav items={navItems} />
    </header>
  );
}
