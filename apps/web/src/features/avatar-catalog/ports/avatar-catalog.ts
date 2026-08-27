import type { AvatarCatalogQuery, AvatarCatalogResult, AvatarDetail, AvatarSetDetail } from '../domain';

export interface AvatarCatalogPort {
  listAvatarSets(query?: AvatarCatalogQuery): Promise<AvatarCatalogResult>;
  getAvatarSetBySlug(slug: string): Promise<AvatarSetDetail | null>;
  getAvatarByRoute(setSlug: string, avatarSlug: string): Promise<AvatarDetail | null>;
}
