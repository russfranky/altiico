import type { AvatarCatalogPort } from '../ports/avatar-catalog';
import { localAvatarCatalogAdapter } from '../adapters/local/adapter';

export const avatarCatalog: AvatarCatalogPort = localAvatarCatalogAdapter;
