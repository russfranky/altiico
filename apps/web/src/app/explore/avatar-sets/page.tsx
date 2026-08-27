import type { Metadata } from 'next';
import { SiteHeader } from '@/components/site-header';
import { avatarCatalog } from '@/features/avatar-catalog/runtime/catalog';
import { AvatarCatalogScreen } from '@/features/avatar-catalog/screens/avatar-catalog-screen';

export const metadata: Metadata = {
  title: 'Avatar Sets',
  description: 'Explore the Altiico avatar-set catalog structure before live Hubzz catalog data is connected.',
};

export default async function AvatarSetsPage() {
  const catalog = await avatarCatalog.listAvatarSets();
  return (
    <>
      <a className="skipLink" href="#catalog-content">Skip to catalog</a>
      <main className="siteShell"><SiteHeader /><AvatarCatalogScreen items={catalog.items} provenance={catalog.provenance} /></main>
    </>
  );
}
