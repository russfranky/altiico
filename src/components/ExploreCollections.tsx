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

  // Category sidebar was removed 2026-04-24 — live API data had no meaningful
  // taxonomy (was just chain origin shown as category). Restore when there's a
  // real editorial/genre categorization. Chains are shown as per-card badges.
  const filteredCollections = useMemo(() => {
    return collections.filter((collection) => {
      const matchesSearch =
        collection.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (collection.description?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false);
      return matchesSearch;
    });
  }, [collections, searchTerm]);

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
            <span className="text-primary font-medium">Avatar Sets</span>
          </nav>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground">
                Avatar Sets
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                {loading ? 'Loading...' : `${collections.length} indexed`}
              </p>
            </div>
            <div className="flex gap-3">
              <Input
                placeholder="Search avatar sets..."
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
          {/* Collection grid — sidebar removed until real taxonomy lands */}
          <main className="flex-1 min-w-0">

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
                              {collection.items} units{collection.assets3D === 'Coming Soon' ? ` · ${collection.assets3D}` : ''}
                            </p>
                          </div>
                        </div>
                        <div className="absolute top-2 right-2 text-xs font-medium px-2 py-1 rounded-md bg-background/90 text-foreground">
                          {collection.items}
                        </div>
                      </div>
                      <div className="p-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          {collection.chain && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground uppercase tracking-wide">
                              {collection.chain}
                            </span>
                          )}
                          {collection.license && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-600/15 text-emerald-400 uppercase tracking-wide">
                              {collection.license}
                            </span>
                          )}
                        </div>
                        {collection.description && (
                          <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                            {collection.description}
                          </p>
                        )}
                        <span className="inline-block mt-2 text-xs text-primary font-medium group-hover:underline">
                          View avatar set →
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-6 text-center">
                  {filteredCollections.length} of {collections.length} indexed sets
                </p>
              </>
            ) : (
              <Card className="p-16 text-center">
                <h2 className="text-xl font-semibold text-foreground mb-2">
                  No results
                </h2>
                <p className="text-muted-foreground mb-4">
                  No avatar sets match your search
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setSearchTerm('');
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
