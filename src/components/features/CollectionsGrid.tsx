import { Link } from 'react-router-dom';
import CollectionCard from './CollectionCard';

type Collection = {
  name: string;
  items: string;
  banner: string;
  pfp: string;
  assets3D: string;
  category?: string;
};

type Props = {
  collections: Collection[];
  /** Group by category. Use false for previews. */
  groupByCategory?: boolean;
  /** Max items when in preview mode (no grouping). */
  limit?: number;
  showViewAll?: boolean;
};

export default function CollectionsGrid({
  collections,
  groupByCategory = true,
  limit,
  showViewAll = false,
}: Props) {
  const isPreview = limit != null;
  const displayList = isPreview ? collections.slice(0, limit) : collections;

  if (groupByCategory && !isPreview) {
    const categories = [...new Set(collections.map((c) => c.category).filter(Boolean))];
    return (
      <>
        {categories.map((category) => (
          <section key={category} className="mb-16">
            <h2 className="text-xl font-semibold text-foreground mb-6 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary" />
              {category}
            </h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {collections
                .filter((c) => c.category === category)
                .map((collection, idx) => (
                  <CollectionCard key={`${collection.name}-${idx}`} collection={collection} />
                ))}
            </div>
          </section>
        ))}
      </>
    );
  }

  return (
    <>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {displayList.map((collection, idx) => (
          <CollectionCard key={`${collection.name}-${idx}`} collection={collection} />
        ))}
      </div>
      {showViewAll && (
        <div className="text-center mt-8">
          <Link to="/collections" className="text-sm font-medium text-primary hover:underline">
            View all collections →
          </Link>
        </div>
      )}
    </>
  );
}
