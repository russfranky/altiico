import Link from 'next/link';
import type { ReactNode } from 'react';

const nav = [
  { href: '/', label: 'SYSTEM' },
  { href: '/explore/avatar-sets', label: 'EXPLORE' },
  { href: '/explore/avatar-sets/core-entity-lab', label: 'SETS' },
  { href: '#studio', label: 'STUDIO' }
];

export function Wordmark() {
  return <span className="wordmark" aria-label="Altiico"><span>ALT</span><b>ii</b><span>CO</span></span>;
}

export function ProductShell({ children, section = 'PUBLIC SYSTEM' }: { children: ReactNode; section?: string }) {
  return (
    <div className="pageFrame">
      <header className="backgroundNav">
        <Link href="/" className="brandLink"><Wordmark /></Link>
        <nav aria-label="Primary navigation">
          {nav.map((item) => <Link key={item.label} href={item.href}>{item.label}</Link>)}
        </nav>
        <span className="navState"><i />{section}</span>
      </header>
      <main>{children}</main>
      <footer className="pageFooter"><Wordmark /><span>IDENTITY → ASSET → PRESENCE</span><span>PRODUCT SITE / T-008</span></footer>
    </div>
  );
}

export function BentoPanel({ children, className = '', label }: { children: ReactNode; className?: string; label?: string }) {
  return <section className={`bentoPanel ${className}`.trim()}>{label ? <span className="panelLabel">{label}</span> : null}{children}</section>;
}
