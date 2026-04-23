import { useState, useEffect } from 'react';
import AltiiHero from '../components/AltiiHero';
import CollectionsGrid from '../components/features/CollectionsGrid';
import PageSection from '../components/layout/PageSection';
import { avatarService } from '../services/avatarService';
import type { Collection } from '../types';

export default function HomePage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    avatarService.getCollections().then((data) => {
      if (!cancelled) {
        setCollections(data);
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, []);

  return (
    <>
      <AltiiHero />

      <PageSection>
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-foreground">Fresh off the printer</h2>
          <p className="text-muted-foreground mt-1">
            The latest avatar cartridges loaded into the machine.
          </p>
        </div>
        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="animate-pulse rounded-xl border border-border bg-card overflow-hidden">
                <div className="aspect-[16/10] bg-muted/50" />
                <div className="p-4 space-y-2">
                  <div className="h-3 bg-muted/50 rounded w-1/3" />
                  <div className="h-4 bg-muted/50 rounded w-2/3" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <CollectionsGrid
            collections={collections}
            groupByCategory={false}
            limit={6}
            showViewAll
          />
        )}
      </PageSection>
    </>
  );
}
