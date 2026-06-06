// Cherry-picked from hubzz-altiico/src/components/CollectionBrowser/CollectionBrowser.tsx
// Adjusted: uses ApiAvatar. Removed AltiiPreviewModal dependency (not needed here —
// AnimationPreviewPage handles its own selection flow). Removed price sort option.

import React from 'react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import AvatarCardSkeleton from '@/components/AvatarCardSkeleton';
import AvatarCard from './AvatarCard';
import { useCollectionBrowser } from './useCollectionBrowser';
import type { CollectionBrowserProps } from './types';

const CollectionBrowser: React.FC<CollectionBrowserProps> = ({
  mode = 'browse',
  avatars,
  loading = false,
  onSelect,
  onPreview,
  initialCollection = 'All',
  initialSearch = '',
  showCollectionFilter = false,
  itemsPerPage = 60,
  emptyMessage,
  className,
}) => {
  const {
    searchTerm,
    selectedCollection,
    sortBy,
    currentPage,
    filteredAvatars,
    paginatedAvatars,
    totalPages,
    collectionList,
    setSearchTerm,
    setSelectedCollection,
    setSortBy,
    handlePageChange,
    clearFilters,
  } = useCollectionBrowser({ avatars, initialCollection, initialSearch, itemsPerPage });

  const handlePreview = (avatar: import('@/lib/avatarApiTypes').ApiAvatar) => {
    if (onPreview) onPreview(avatar);
  };

  return (
    <div className={cn('flex gap-4', className)}>
      {mode === 'browse' && showCollectionFilter && (
        <aside className="w-48 shrink-0">
          <Card className="p-3 space-y-1">
            <h3 className="font-semibold text-foreground mb-2 text-xs uppercase tracking-wider">Avatar Sets</h3>
            <div className="flex flex-col gap-0.5 max-h-80 overflow-y-auto">
              {collectionList.map((c) => (
                <button
                  key={c}
                  onClick={() => setSelectedCollection(c)}
                  className={cn(
                    'text-left text-xs px-2 py-1.5 rounded-md transition-colors truncate',
                    selectedCollection === c
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  {c}
                </button>
              ))}
            </div>
          </Card>
        </aside>
      )}

      <div className="flex-1 min-w-0">
        <div className="flex gap-2 mb-3">
          <Input
            placeholder="Search avatars..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="flex-1 h-8 text-xs"
          />
          {mode === 'browse' && (
            <Select value={sortBy} onValueChange={(v) => setSortBy(v as 'id' | 'collection')}>
              <SelectTrigger className="w-[110px] h-8 text-xs">
                <SelectValue placeholder="Sort" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="id">Token ID</SelectItem>
                <SelectItem value="collection">Avatar Set</SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-2 gap-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <AvatarCardSkeleton key={i} />
            ))}
          </div>
        ) : paginatedAvatars.length > 0 ? (
          <>
            <div className="grid grid-cols-2 gap-2">
              {paginatedAvatars.map((avatar) => (
                <AvatarCard
                  key={`${avatar.collection_slug}-${avatar.id}`}
                  avatar={avatar}
                  mode={mode}
                  onPreview={onPreview ?? handlePreview}
                  onSelect={onSelect}
                />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-4">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="size-3" />
                </Button>
                <span className="text-xs text-muted-foreground">
                  {currentPage}/{totalPages}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                >
                  <ChevronRight className="size-3" />
                </Button>
              </div>
            )}

            <p className="text-[10px] text-muted-foreground mt-2 text-center">
              {filteredAvatars.length} avatars
            </p>
          </>
        ) : (
          <Card className="p-6 text-center">
            <p className="text-sm text-muted-foreground mb-2">
              {emptyMessage ?? 'No avatars match your filters.'}
            </p>
            <button
              type="button"
              onClick={clearFilters}
              className="text-xs text-primary hover:underline"
            >
              Clear filters
            </button>
          </Card>
        )}
      </div>
    </div>
  );
};

export default CollectionBrowser;
