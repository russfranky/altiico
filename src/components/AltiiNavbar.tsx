import React, { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { VISIBLE_NAV } from '@/config/nav';

const AltiiNavbar = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 max-w-7xl mx-auto items-center justify-between gap-4 px-4">
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2 font-semibold text-foreground hover:text-primary transition-colors">
            altiico
          </Link>

          <div className="hidden md:flex items-center gap-6">
            {VISIBLE_NAV.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Global search + wallet Connect removed 2026-04-24 — both were
              non-functional stubs and users typed into the search box
              expecting results. Restore when each has real wiring. */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setIsOpen(!isOpen)}
          >
            {isOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </Button>
        </div>
      </div>

      {isOpen && (
        <div className="md:hidden border-t border-border bg-background">
          <div className="flex flex-col gap-2 max-w-7xl mx-auto px-4 py-4">
            {VISIBLE_NAV.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setIsOpen(false)}
                className="px-4 py-2 text-sm font-medium text-foreground hover:bg-muted rounded-lg"
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
};

export default AltiiNavbar;
