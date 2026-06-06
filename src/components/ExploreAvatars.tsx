import React, { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react';
import type { Avatar } from '../types';
import { avatarService } from '../services/avatarService';
import { PLACEHOLDER_IMG } from '../data/altiiData';
import { Link, useSearchParams } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import AvatarCardSkeleton from './AvatarCardSkeleton';

// Lazy-load the preview modal since it pulls in AltiiViewer -> three.js + VRM
const AltiiPreviewModal = lazy(() => import('./AltiiPreviewModal'));

const PAGE_SIZE = 60;

const ExploreAvatars = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const collectionFromUrl = searchParams.get('collection');
  const searchFromUrl = searchParams.get('q') ?? '';

  const [avatars, setAvatars] = useState<Avatar[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [searchTerm, setSearchTerm] = useState(searchFromUrl);
  const [selectedCollection, setSelectedCollection] = useState(collectionFromUrl || 'All');
  const [previewAvatar, setPreviewAvatar] = useState<Avatar | null>(null);
  const [collections, setCollections] = useState<{ slug: string; name: string; avatar_count: number }[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Load collections from API
  useEffect(() => {
    avatarService.getApiCollections().then(setCollections);
  }, []);

  // Sync URL params
  useEffect(() => {
    if (collectionFromUrl) setSelectedCollection(collectionFromUrl);
  }, [collectionFromUrl]);

  // Search function
  const doSearch = useCallback(async (search: string, collection: string, offset = 0, append = false) => {
    if (!append) setLoading(true);
    else setLoadingMore(true);

    const result = await avatarService.searchAvatars({
      search: search || undefined,
      collection: collection === 'All' ? undefined : collection,
      limit: PAGE_SIZE,
      offset,
    });

    if (append) {
      setAvatars(prev => [...prev, ...result.avatars]);
    } else {
      setAvatars(result.avatars);
    }
    setTotal(result.total);
    setLoading(false);
    setLoadingMore(false);
  }, []);

  // Initial load + search/filter changes
  useEffect(() => {
    doSearch(searchTerm, selectedCollection);
  }, [selectedCollection]);

  // Debounced search
  const handleSearchChange = (value: string) => {
    setSearchTerm(value);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (value) next.set('q', value);
      else next.delete('q');
      return next;
    }, { replace: true });

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      doSearch(value, selectedCollection);
    }, 300);
  };

  const handleCollectionChange = (c: string) => {
    setSelectedCollection(c);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (c === 'All') next.delete('collection');
      else next.set('collection', c);
      return next;
    }, { replace: true });
  };

  const loadMore = () => {
    doSearch(searchTerm, selectedCollection, avatars.length, true);
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-card/30">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
            <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
            <span>/</span>
            <span className="text-primary font-medium">Avatars</span>
          </nav>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground">Avatars</h1>
              <p className="text-sm text-muted-foreground mt-1">
                {total.toLocaleString()} assets indexed
              </p>
            </div>
            <div className="flex gap-3 flex-wrap">
              <Input
                placeholder="Search..."
                value={searchTerm}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-48 sm:w-56"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-8">
          <aside className="w-56 shrink-0 hidden lg:block">
            <Card className="sticky top-24 p-4 space-y-6">
              <div>
                <h3 className="font-semibold text-foreground mb-3 text-sm">Avatar Sets</h3>
                <div className="flex flex-col gap-0.5 max-h-64 overflow-y-auto">
                  <button
                    onClick={() => handleCollectionChange('All')}
                    className={cn(
                      'text-left text-sm px-3 py-2 rounded-lg transition-colors',
                      selectedCollection === 'All'
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                    )}
                  >
                    All
                  </button>
                  {collections.map((c) => (
                    <button
                      key={c.slug}
                      onClick={() => handleCollectionChange(c.slug)}
                      className={cn(
                        'text-left text-sm px-3 py-2 rounded-lg transition-colors',
                        selectedCollection === c.slug
                          ? 'bg-primary text-primary-foreground'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                      )}
                    >
                      {c.name}
                      <span className="text-xs ml-1 opacity-60">({c.avatar_count})</span>
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          </aside>

          <main className="flex-1 min-w-0">
            {/* Mobile filters */}
            <div className="lg:hidden mb-6">
              <Card className="p-4">
                <details>
                  <summary className="font-medium cursor-pointer text-sm">Filters</summary>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      onClick={() => handleCollectionChange('All')}
                      className={cn('text-xs px-3 py-1.5 rounded-lg', selectedCollection === 'All' ? 'bg-primary text-primary-foreground' : 'bg-muted')}
                    >
                      All
                    </button>
                    {collections.map((c) => (
                      <button
                        key={c.slug}
                        onClick={() => handleCollectionChange(c.slug)}
                        className={cn('text-xs px-3 py-1.5 rounded-lg', selectedCollection === c.slug ? 'bg-primary text-primary-foreground' : 'bg-muted')}
                      >
                        {c.name}
                      </button>
                    ))}
                  </div>
                </details>
              </Card>
            </div>

            {loading ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3 sm:gap-4">
                {Array.from({ length: 14 }).map((_, i) => (
                  <AvatarCardSkeleton key={i} />
                ))}
              </div>
            ) : avatars.length > 0 ? (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3 sm:gap-4">
                  {avatars.map((avatar) => (
                    <article
                      key={`${avatar.source}-${avatar.id}`}
                      className="group rounded-lg border border-border bg-card overflow-hidden hover:border-primary/50 hover:shadow-md transition-all"
                    >
                      <button type="button" onClick={() => setPreviewAvatar(avatar)} className="block w-full text-left">
                        <div className="aspect-square relative bg-muted/30 overflow-hidden cursor-pointer">
                          <img
                            src={avatar.image || PLACEHOLDER_IMG}
                            alt={avatar.name}
                            loading="lazy"
                            decoding="async"
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                            onError={(e) => { e.currentTarget.src = PLACEHOLDER_IMG; }}
                          />
                          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                          <div className="absolute bottom-2 left-2 right-2 text-white text-xs font-medium truncate opacity-0 group-hover:opacity-100 transition-opacity">
                            {avatar.collection}
                          </div>
                          <div className="absolute top-2 left-2 flex gap-1 flex-wrap">
                            <span className="text-[10px] px-2 py-0.5 rounded bg-black/60 text-white/90 truncate max-w-[80%]">
                              {avatar.collection}
                            </span>
                            {avatar.license && (
                              <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-600/80 text-white">{avatar.license}</span>
                            )}
                          </div>
                        </div>
                      </button>
                      <div className="p-2 sm:p-2.5">
                        <div className="text-xs font-semibold text-foreground truncate">{avatar.name}</div>
                        {avatar.opensea && (
                          <div className="mt-1.5">
                            <a
                              href={avatar.opensea}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-[11px] text-muted-foreground hover:text-foreground"
                            >
                              Market →
                            </a>
                          </div>
                        )}
                      </div>
                    </article>
                  ))}
                </div>

                <div className="text-center mt-8 space-y-2">
                  <p className="text-xs text-muted-foreground">
                    Showing {avatars.length} of {total.toLocaleString()} avatars
                  </p>
                  {avatars.length < total && (
                    <button
                      onClick={loadMore}
                      disabled={loadingMore}
                      className="text-sm text-primary hover:underline disabled:opacity-50"
                    >
                      {loadingMore ? 'Loading...' : 'Load more'}
                    </button>
                  )}
                </div>
              </>
            ) : (
              <Card className="p-16 text-center">
                <h2 className="text-xl font-semibold text-foreground mb-2">No results</h2>
                <p className="text-muted-foreground mb-4">No indexed assets match your filters</p>
                <button
                  type="button"
                  onClick={() => { setSearchTerm(''); handleCollectionChange('All'); }}
                  className="text-sm text-primary hover:underline"
                >
                  Clear filters
                </button>
              </Card>
            )}
          </main>
        </div>
      </div>

      {previewAvatar && (
        <Suspense fallback={null}>
          <AltiiPreviewModal
            isOpen={!!previewAvatar}
            onClose={() => setPreviewAvatar(null)}
            avatar={previewAvatar}
          />
        </Suspense>
      )}
    </div>
  );
};

export default ExploreAvatars;
