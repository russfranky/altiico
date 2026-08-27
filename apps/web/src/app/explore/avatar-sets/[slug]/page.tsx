import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { SiteHeader } from '@/components/site-header';
import { avatarCatalog } from '@/features/avatar-catalog/runtime/catalog';
import { AvatarSetDetailScreen } from '@/features/avatar-catalog/screens/avatar-set-detail-screen';

export async function generateStaticParams() {
  const catalog = await avatarCatalog.listAvatarSets();
  return catalog.items.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const item = await avatarCatalog.getAvatarSetBySlug(slug);
  return item ? { title: item.displayName, description: item.description } : { title: 'Avatar Set Not Found' };
}

export default async function AvatarSetDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const item = await avatarCatalog.getAvatarSetBySlug(slug);
  if (!item) notFound();
  return <><a className="skipLink" href="#set-detail-content">Skip to set detail</a><main className="siteShell"><SiteHeader /><div id="set-detail-content" tabIndex={-1}><AvatarSetDetailScreen item={item} /></div></main></>;
}
