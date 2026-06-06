import React, { useState, useMemo, useEffect, useCallback, useRef, lazy, Suspense } from 'react';
import * as Sentry from '@sentry/react';
import { Link, useParams } from 'react-router-dom';
import { PLACEHOLDER_IMG } from '../data/altiiData';
import { extractCollectionTraits, filterCollectionAvatars } from '../lib/collectionUtils';
import { avatarService } from '../services/avatarService';
import { obs } from '@/lib/obs';
import type { Avatar } from '../types';
import type { Collection } from '../types';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import AvatarCardSkeleton from './AvatarCardSkeleton';

const AltiiPreviewModal = lazy(() => import('./AltiiPreviewModal'));

const ITEMS_PER_PAGE = 60;

/**
 * Collection detail page — server-side paginated.
 * Each page change fetches from the API with offset/limit.
 */
const CollectionDetail = () => {
  const { slug } = useParams<{ slug: string }>();
  const [collection, setCollection] = useState<Collection | null>(null);
  const [collectionLoading, setCollectionLoading] = useState(true);
  const [avatars, setAvatars] = useState<Avatar[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [previewAvatar, setPreviewAvatar] = useState<Avatar | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search input (300ms)
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1); // Reset to page 1 on search
    }, 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [searchTerm]);

  // Fetch collection metadata
  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    const load = async () => {
      setCollectionLoading(true);
      const data = await avatarService.getCollectionBySlug(slug);
      if (!cancelled) {
        setCollection(data);
        setCollectionLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [slug]);

  // Fetch avatars — server-side paginated
  const fetchAvatars = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    try {
      const offset = (currentPage - 1) * ITEMS_PER_PAGE;
      const data = await avatarService.getCollectionAvatars(slug, {
        limit: ITEMS_PER_PAGE,
        offset,
        search: debouncedSearch || undefined,
      });
      setAvatars(data.avatars);
      setTotal(data.total);
      setHasMore(data.has_more);
    } catch (err) {
      Sentry.captureException(err, { tags: { kind: 'api.collection_detail', slug: slug ?? 'unknown' } });
      obs.exception('api.collection_detail', err, { slug: slug ?? 'unknown', page: currentPage });
      setAvatars([]);
      setTotal(0);
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, [slug, currentPage, debouncedSearch]);

  useEffect(() => {
    fetchAvatars();
  }, [fetchAvatars]);

  const totalPages = Math.max(1, Math.ceil(total / ITEMS_PER_PAGE));

  const onImgError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.src = PLACEHOLDER_IMG;
  };

  const handlePageChange = (page: number) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
    window.scrollTo({ top: 400, behavior: 'smooth' });
  };

  const isLoading = collectionLoading || loading;

  if (!slug || (!collection && !isLoading)) {
    return (
      <div className="min-h-screen bg-background">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <Card className="p-16 text-center">
            <h1 className="text-2xl font-bold text-foreground mb-2">
              Collection not found
            </h1>
            <p className="text-muted-foreground mb-4">
              The collection you're looking for doesn't exist or hasn't been indexed.
            </p>
            <Link
              to="/explore/collections"
              className="text-primary hover:underline font-medium"
            >
              &larr; Back to collections
            </Link>
          </Card>
        </div>
      </div>
    );
  }

  if (!collection) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-muted-foreground animate-pulse">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Breadcrumb */}
      <div className="border-b border-border bg-card/30">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <nav className="flex items-center gap-2 text-sm text-muted-foreground">
            <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
            <span>/</span>
            <Link to="/explore" className="hover:text-foreground transition-colors">Explore</Link>
            <span>/</span>
            <Link to="/explore/collections" className="hover:text-foreground transition-colors">Avatar Sets</Link>
            <span>/</span>
            <span className="text-primary font-medium">{collection.name}</span>
          </nav>
        </div>
      </div>

      {/* Collection header */}
      <div className="relative">
        <div className="aspect-[21/9] sm:aspect-[3/1] max-h-[320px] md:max-h-[420px] lg:max-h-[520px] overflow-hidden bg-muted/30">
          <img
            src={(collection.banner || PLACEHOLDER_IMG).replace(/\?fit=inside(&|$)/, "?w=1920$1").replace(/\?fit=inside$/, "")}
            alt={collection.name}
            className="w-full h-full object-cover"
            onError={onImgError}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/50 to-transparent" />
        </div>
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="relative -mt-20 sm:-mt-24 pb-8 flex flex-col sm:flex-row sm:items-end gap-6">
            <img
              src={collection.pfp || PLACEHOLDER_IMG}
              alt=""
              className="w-24 h-24 sm:w-32 sm:h-32 rounded-xl border-4 border-background object-cover shadow-lg shrink-0"
              onError={onImgError}
            />
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-foreground">
                {collection.name}
              </h1>
              <div className="flex flex-wrap items-center gap-4 mt-2 text-sm text-muted-foreground">
                <span>{collection.items} units</span>
                {collection.chain && (
                  <>
                    <span className="text-border">&middot;</span>
                    <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded bg-muted">
                      {collection.chain}
                    </span>
                  </>
                )}
                {collection.category && (
                  <>
                    <span className="text-border">&middot;</span>
                    <span>{collection.category}</span>
                  </>
                )}
                {(collection as any).license && (
                  <>
                    <span className="text-border">&middot;</span>
                    <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded bg-emerald-600/15 text-emerald-400">
                      {(collection as any).license}
                    </span>
                  </>
                )}
                {collection.assets3D === 'Coming Soon' && (
                  <>
                    <span className="text-border">&middot;</span>
                    <span className="text-muted-foreground">{collection.assets3D}</span>
                  </>
                )}
              </div>
              {collection.description && (
                <p className="mt-3 text-sm text-muted-foreground max-w-2xl">{collection.description}</p>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-2 mt-4">
                {collection.contract && (
                  <a
                    href={`https://etherscan.io/address/${collection.contract}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-primary hover:underline font-medium"
                  >
                    Contract
                  </a>
                )}
                {collection.contract && (
                  <a
                    href={`https://opensea.io/collection/${collection.slug}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-primary hover:underline font-medium"
                  >
                    OpenSea
                  </a>
                )}
                <Link
                  to={`/explore/assets/avatars?collection=${encodeURIComponent(collection.slug || collection.name)}`}
                  className="text-sm text-primary hover:underline font-medium"
                >
                  View assets
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <h2 className="text-xl font-semibold text-foreground">
            {total > 0 ? `${total.toLocaleString()} avatars` : 'Avatars'}
          </h2>
          <Input
            placeholder="Search in set..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full sm:w-56"
          />
        </div>

        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3 sm:gap-4">
            {Array.from({ length: 12 }).map((_, i) => (
              <AvatarCardSkeleton key={i} />
            ))}
          </div>
        ) : avatars.length > 0 ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3 sm:gap-4">
              {avatars.map((avatar) => (
                <article
                  key={`${avatar.source || 'static'}-${avatar.id}`}
                  className="group rounded-lg border border-border bg-card overflow-hidden hover:border-primary/50 hover:shadow-md transition-all"
                >
                  <button
                    type="button"
                    onClick={() => setPreviewAvatar(avatar)}
                    className="block w-full text-left"
                  >
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
                        {avatar.name}
                      </div>
                    </div>
                  </button>
                  <div className="p-2 sm:p-2.5">
                    <div className="text-xs font-semibold text-foreground truncate">#{avatar.id}</div>
                    <div className="text-[11px] text-muted-foreground truncate mt-0.5">{avatar.name}</div>
                    <div className="mt-1.5 flex gap-1.5 flex-wrap">
                      <button
                        type="button"
                        onClick={() => setPreviewAvatar(avatar)}
                        className="text-[11px] text-primary hover:underline"
                      >
                        Preview
                      </button>
                      {avatar.opensea && (
                        <a
                          href={avatar.opensea}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[11px] text-muted-foreground hover:text-foreground"
                        >
                          Market
                        </a>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-12">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <div className="flex items-center gap-2">
                  {currentPage > 2 && (
                    <>
                      <Button variant="ghost" size="sm" onClick={() => handlePageChange(1)}>1</Button>
                      {currentPage > 3 && <span className="text-muted-foreground">...</span>}
                    </>
                  )}
                  {[currentPage - 1, currentPage, currentPage + 1]
                    .filter(p => p >= 1 && p <= totalPages)
                    .map(p => (
                      <Button
                        key={p}
                        variant={p === currentPage ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => handlePageChange(p)}
                      >
                        {p}
                      </Button>
                    ))
                  }
                  {currentPage < totalPages - 1 && (
                    <>
                      {currentPage < totalPages - 2 && <span className="text-muted-foreground">...</span>}
                      <Button variant="ghost" size="sm" onClick={() => handlePageChange(totalPages)}>{totalPages}</Button>
                    </>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                >
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            )}

            <p className="text-xs text-muted-foreground mt-6 text-center">
              Showing {((currentPage - 1) * ITEMS_PER_PAGE) + 1}&ndash;{Math.min(currentPage * ITEMS_PER_PAGE, total)} of {total.toLocaleString()} from {collection.name}
            </p>
          </>
        ) : (
          <Card className="p-16 text-center">
            <h2 className="text-xl font-semibold text-foreground mb-2">No assets found</h2>
            <p className="text-muted-foreground mb-4">
              {debouncedSearch ? 'No assets match your search.' : `No indexed assets for ${collection.name} yet.`}
            </p>
            {debouncedSearch && (
              <button
                type="button"
                onClick={() => { setSearchTerm(''); setDebouncedSearch(''); }}
                className="text-sm text-primary hover:underline"
              >
                Clear search
              </button>
            )}
          </Card>
        )}
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

export default CollectionDetail;
