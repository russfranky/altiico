import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import '@altiico/brand/tokens.css';
import '@altiico/ui/styles.css';
import './globals.css';

export const metadata: Metadata = {
  title: { default: 'Altiico — Avatar Identity & Asset System', template: '%s / Altiico' },
  description: 'Discover, verify, and operate avatar identities for Hubzz through the Altiico system.',
};

export const viewport: Viewport = { colorScheme: 'dark', themeColor: '#0B0D10' };

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
