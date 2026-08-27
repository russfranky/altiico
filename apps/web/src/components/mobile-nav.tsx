'use client';

import { useState } from 'react';
import { SystemLabel } from '@altiico/ui';

type NavItem = { href: string; label: string };

export function MobileNav({ items }: { items: NavItem[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mobileNav">
      <button
        className="mobileNavTrigger"
        type="button"
        aria-expanded={open}
        aria-controls="mobile-primary-navigation"
        onClick={() => setOpen((current) => !current)}
      >
        <SystemLabel tone={open ? 'signal' : 'muted'}>{open ? 'Close' : 'Menu'}</SystemLabel>
        <span className="mobileNavGlyph" aria-hidden="true"><span /><span /></span>
      </button>
      {open ? (
        <nav id="mobile-primary-navigation" className="mobileNavPanel" aria-label="Mobile navigation">
          {items.map((item, index) => (
            <a key={item.label} className="mobileNavLink" href={item.href} onClick={() => setOpen(false)}>
              <SystemLabel tone="signal">{String(index + 1).padStart(2, '0')}</SystemLabel>
              <span>{item.label}</span><span aria-hidden="true">→</span>
            </a>
          ))}
        </nav>
      ) : null}
    </div>
  );
}
