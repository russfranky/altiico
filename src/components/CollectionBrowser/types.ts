// Cherry-picked from hubzz-altiico/src/components/CollectionBrowser/types.ts
// Adjusted: Avatar import uses altiico's local ApiAvatar type (not the static data Avatar).

import type { ApiAvatar } from '@/lib/avatarApiTypes';

export type BrowserMode = 'browse' | 'select';

export interface CollectionBrowserProps {
  mode?: BrowserMode;
  avatars: ApiAvatar[];
  loading?: boolean;
  onSelect?: (avatar: ApiAvatar) => void;
  onPreview?: (avatar: ApiAvatar) => void;
  initialCollection?: string;
  initialSearch?: string;
  showCollectionFilter?: boolean;
  traits?: Record<string, string[]>;
  itemsPerPage?: number;
  emptyMessage?: string;
  className?: string;
}

export interface AvatarCardProps {
  avatar: ApiAvatar;
  mode: BrowserMode;
  onPreview: (avatar: ApiAvatar) => void;
  onSelect?: (avatar: ApiAvatar) => void;
}

export interface UseBrowserState {
  searchTerm: string;
  selectedCollection: string;
  sortBy: 'id' | 'collection';
  currentPage: number;
  filteredAvatars: ApiAvatar[];
  paginatedAvatars: ApiAvatar[];
  totalPages: number;
  setSearchTerm: (v: string) => void;
  setSelectedCollection: (v: string) => void;
  setSortBy: (v: 'id' | 'collection') => void;
  handlePageChange: (page: number) => void;
  clearFilters: () => void;
  collectionList: string[];
}
