import React, { useState, useMemo, useEffect } from 'react';
import * as Sentry from '@sentry/react';
import { Link } from 'react-router-dom';
import { PLACEHOLDER_IMG } from '../data/altiiData';
import { avatarService } from '../services/avatarService';
import { obs } from '@/lib/obs';
import type { Collection } from '../types';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { toCollectionSlug } from '@/lib/collectionUtils';

/**
 * Explore-style collections index — vipe.io explore/collections pattern.
 * Image-forward grid, category filters, indexed collection cards.
 * Fetches from the avatar API; falls back to static data on error.
 */
const ExploreCollections = () => {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await avatarService.getCollections();
        if (!cancelled) setCollections(data);
      } catch (err) {
        Sentry.captureException(err, { tags: { kind: 'page.explore_collections' } });
        obs.exception('page.explore_collections', err);
        if (!cancelled) setError('Failed to load collections');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const categories = useMemo(() => {
    const cats = [...new Set(collections.map((c) => c.category).filter(Boolean))];
    return ['All', ...cats] as string[];
  }, [collections]);

  const filteredCollections = useMemo(() => {
    return collections.filter((collection) => {
      const matchesSearch =
        collection.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (collection.description?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false);
      const matchesCategory =
        selectedCategory === 'All' || collection.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [collections, searchTerm, selectedCategory]);

  const onImgError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.src = PLACEHOLDER_IMG;
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Breadcrumb + header — explore path */}
      <div className="border-b border-border bg-card/30">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
            <Link to="/" className="hover:text-foreground transition-colors">
              Home
            </Link>
            <span>/</span>
            <Link to="/explore" className="hover:text-foreground transition-colors">
              Explore
            </Link>
            <span>/</span>
            <span className="text-primary font-medium">Collections</span>
          </nav>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground">
                Indexed Collections
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                {loading ? 'Loading...' : `${collections.length} collections`} · Verified provenance
              </p>
            </div>
            <div className="flex gap-3">
              <Input
                placeholder="Search collections..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-48 sm:w-56"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-8">
          {/* Filters sidebar */}
          <aside className="w-56 shrink-0 hidden lg:block">
            <Card className="sticky top-24 p-4 space-y-6">
              <div>
                <h3 className="font-semibold text-foreground mb-3 text-sm">
                  Categories
                </h3>
                <div className="flex flex-col gap-0.5 max-h-64 overflow-y-auto">
                  {categories.map((c) => (
                    <button
                      key={c}
                      onClick={() => setSelectedCategory(c)}
                      className={cn(
                        'text-left text-sm px-3 py-2 rounded-lg transition-colors',
                        selectedCategory === c
                          ? 'bg-primary text-primary-foreground'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                      )}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          </aside>

          {/* Collection grid */}
          <main className="flex-1 min-w-0">
            {/* Mobile category filters */}
            <div className="lg:hidden mb-6">
              <div className="flex flex-wrap gap-2">
                {categories.map((c) => (
                  <button
                    key={c}
                    onClick={() => setSelectedCategory(c)}
                    className={cn(
                      'text-xs px-3 py-1.5 rounded-lg',
                      selectedCategory === c
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted'
                    )}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Card key={i} className="overflow-hidden animate-pulse">
                    <div className="aspect-[16/10] bg-muted/50" />
                    <div className="p-4 space-y-2">
                      <div className="h-3 bg-muted/50 rounded w-1/3" />
                      <div className="h-4 bg-muted/50 rounded w-2/3" />
                    </div>
                  </Card>
                ))}
              </div>
            ) : error ? (
              <Card className="p-16 text-center">
                <h2 className="text-xl font-semibold text-foreground mb-2">
                  Error
                </h2>
                <p className="text-muted-foreground mb-4">{error}</p>
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="text-sm text-primary hover:underline"
                >
                  Retry
                </button>
              </Card>
            ) : filteredCollections.length > 0 ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                  {filteredCollections.map((collection: Collection, idx: number) => (
                    <Link
                      key={`${collection.name}-${idx}`}
                      to={`/explore/collections/${collection.slug || toCollectionSlug(collection.name)}`}
                      className="group rounded-xl border border-border bg-card overflow-hidden hover:border-primary/50 hover:shadow-lg transition-all block"
                    >
                      <div className="relative aspect-[16/10] overflow-hidden">
                        <img
                          src={collection.banner || PLACEHOLDER_IMG}
                          alt={collection.name}
                          loading="lazy"
                          decoding="async"
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          onError={onImgError}
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
                        <div className="absolute bottom-2 left-2 right-2 flex items-end gap-2">
                          <img
                            src={collection.pfp || PLACEHOLDER_IMG}
                            alt=""
                            loading="lazy"
                            decoding="async"
                            className="w-12 h-12 rounded-lg object-cover border border-white/20 shrink-0"
                            onError={onImgError}
                          />
                          <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-white truncate">
                              {collection.name}
                            </h3>
                            <p className="text-xs text-white/80">
                              {collection.items} units · {collection.assets3D}
                            </p>
                          </div>
                        </div>
                        <div className="absolute top-2 right-2 text-xs font-medium px-2 py-1 rounded-md bg-background/90 text-foreground">
                          {collection.items}
                        </div>
                      </div>
                      <div className="p-4">
                        {collection.category && (
                          <span className="text-xs text-muted-foreground">
                            {collection.category}
                          </span>
                        )}
                        {collection.description && (
                          <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                            {collection.description}
                          </p>
                        )}
                        <span className="inline-block mt-2 text-xs text-primary font-medium group-hover:underline">
                          View collection →
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-6 text-center">
                  {filteredCollections.length} of {collections.length} indexed collections
                </p>
              </>
            ) : (
              <Card className="p-16 text-center">
                <h2 className="text-xl font-semibold text-foreground mb-2">
                  No results
                </h2>
                <p className="text-muted-foreground mb-4">
                  No collections match your search
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setSearchTerm('');
                    setSelectedCategory('All');
                  }}
                  className="text-sm text-primary hover:underline"
                >
                  Clear filters
                </button>
              </Card>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default ExploreCollections;
