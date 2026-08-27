import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { SiteHeader } from '@/components/site-header';
import { avatarCatalog } from '@/features/avatar-catalog/runtime/catalog';
import { AvatarDetailScreen } from '@/features/avatar-catalog/screens/avatar-detail-screen';

export async function generateStaticParams() {
  const catalog = await avatarCatalog.listAvatarSets();
  const nested = await Promise.all(catalog.items.map(async (set) => {
    const detail = await avatarCatalog.getAvatarSetBySlug(set.slug);
    return detail?.avatarSlots.map((avatar) => ({ slug: set.slug, avatarSlug: avatar.avatarSlug })) ?? [];
  }));
  return nested.flat();
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string; avatarSlug: string }> }): Promise<Metadata> {
  const { slug, avatarSlug } = await params;
  const item = await avatarCatalog.getAvatarByRoute(slug, avatarSlug);
  return item ? { title: item.displayName, description: item.description } : { title: 'Avatar Not Found' };
}

export default async function AvatarDetailPage({ params }: { params: Promise<{ slug: string; avatarSlug: string }> }) {
  const { slug, avatarSlug } = await params;
  const [item, set] = await Promise.all([avatarCatalog.getAvatarByRoute(slug, avatarSlug), avatarCatalog.getAvatarSetBySlug(slug)]);
  if (!item || !set) notFound();
  return <><a className="skipLink" href="#avatar-detail-content">Skip to avatar detail</a><main className="siteShell"><SiteHeader /><div id="avatar-detail-content" tabIndex={-1}><AvatarDetailScreen item={item} set={set} /></div></main></>;
}
