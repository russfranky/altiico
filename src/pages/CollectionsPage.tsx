import { useState, useEffect } from 'react';
import * as Sentry from '@sentry/react';
import { Link } from 'react-router-dom';
import { communityMembers, PLACEHOLDER_IMG } from '../data/altiiData';
import { toCollectionSlug } from '../lib/collectionUtils';
import { avatarService } from '../services/avatarService';
import { obs } from '@/lib/obs';
import type { Collection } from '../types';
import PageSection from '../components/layout/PageSection';
import { Card } from '@/components/ui/card';

const onImgError = (e: React.SyntheticEvent<HTMLImageElement>) => {
  e.currentTarget.src = PLACEHOLDER_IMG;
};

export default function CollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await avatarService.getCollections();
        if (!cancelled) setCollections(data);
      } catch (err) {
        Sentry.captureException(err, { tags: { kind: 'page.collections' } });
        obs.exception('page.collections', err);
        if (!cancelled) setError('Failed to load collections');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const categories = [...new Set(collections.map((c) => c.category).filter(Boolean))].sort();

  return (
    <>
      <PageSection>
        <div className="mb-10">
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">
            Collections
          </h1>
          <p className="text-muted-foreground mt-1">
            {loading ? 'Loading...' : `${collections.length} indexed`} · Verified provenance
          </p>
        </div>

        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="animate-pulse flex items-center gap-4 p-5 border border-border rounded-lg">
                <div className="w-12 h-12 rounded-lg bg-muted/50 shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-muted/50 rounded w-1/4" />
                  <div className="h-3 bg-muted/50 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <Card className="p-16 text-center">
            <h2 className="text-xl font-semibold text-foreground mb-2">Error</h2>
            <p className="text-muted-foreground mb-4">{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="text-sm text-primary hover:underline"
            >
              Retry
            </button>
          </Card>
        ) : (
          categories.map((category) => (
            <section key={category} className="mb-12">
              <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">
                {category}
              </h2>
              <div className="border border-border rounded-lg divide-y divide-border overflow-hidden">
                {collections
                  .filter((c) => c.category === category)
                  .map((c, idx) => (
                    <Link
                      key={`${c.slug || c.name}-${idx}`}
                      to={`/explore/collections/${c.slug || toCollectionSlug(c.name)}`}
                      className="flex items-center gap-4 sm:gap-6 p-4 sm:p-5 hover:bg-muted/30 transition-colors group"
                    >
                      <img
                        src={c.pfp || PLACEHOLDER_IMG}
                        alt=""
                        loading="lazy"
                        decoding="async"
                        className="w-12 h-12 rounded-lg object-cover border border-border shrink-0"
                        onError={onImgError}
                      />
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-foreground group-hover:text-primary transition-colors">
                          {c.name}
                        </h3>
                        {c.description && (
                          <p className="text-sm text-muted-foreground mt-0.5 line-clamp-1">
                            {c.description}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-4 sm:gap-6 shrink-0 text-sm">
                        <span className="text-muted-foreground w-16 sm:w-20 text-right">
                          {c.items}
                        </span>
                        <span
                          className={`w-20 text-right text-xs font-medium ${
                            c.assets3D !== 'Coming Soon' ? 'text-emerald-600' : 'text-amber-600'
                          }`}
                        >
                          {c.assets3D}
                        </span>
                        <span className="text-primary text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                          View →
                        </span>
                      </div>
                    </Link>
                  ))}
              </div>
            </section>
          ))
        )}
      </PageSection>

      <PageSection variant="muted">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Community
        </h2>
        <div className="flex flex-wrap gap-3">
          {communityMembers.map((member, idx) => (
            <div
              key={idx}
              className="flex items-center gap-3 rounded-lg border border-border bg-card/50 px-4 py-2.5"
            >
              <img
                src={member.pfp || PLACEHOLDER_IMG}
                alt={member.name}
                loading="lazy"
                decoding="async"
                className="w-8 h-8 rounded-full object-cover shrink-0"
                onError={onImgError}
              />
              <div>
                <span className="text-sm font-medium text-foreground">{member.name}</span>
                <span className="text-xs text-muted-foreground ml-2">{member.role}</span>
              </div>
            </div>
          ))}
        </div>
      </PageSection>
    </>
  );
}
