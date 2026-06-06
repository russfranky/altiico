import { Link } from 'react-router-dom';
import { PLACEHOLDER_IMG } from '../../data/altiiData';
import { toCollectionSlug } from '../../lib/collectionUtils';

type Collection = {
  name: string;
  items: string;
  banner: string;
  pfp: string;
  assets3D: string;
  category?: string;
};

const onImgError = (e: React.SyntheticEvent<HTMLImageElement>) => { e.currentTarget.src = PLACEHOLDER_IMG; };

export default function CollectionCard({ collection }: { collection: Collection }) {
  return (
    <Link
      to={`/explore/collections/${toCollectionSlug(collection.name)}`}
      className="block rounded-lg border border-border bg-card overflow-hidden hover:border-primary/40 transition-colors"
    >
      <div className="relative aspect-[16/10]">
        <img src={collection.banner || PLACEHOLDER_IMG} alt={collection.name} loading="lazy" decoding="async" className="w-full h-full object-cover" onError={onImgError} />
        <div className="absolute bottom-2 right-2 text-xs font-medium px-2 py-1 rounded bg-background/90 text-foreground">
          {collection.items}
        </div>
      </div>
      <div className="p-3 flex gap-3">
        <img src={collection.pfp || PLACEHOLDER_IMG} alt="" loading="lazy" decoding="async" className="w-10 h-10 rounded-lg object-cover border border-border shrink-0" onError={onImgError} />
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-foreground truncate text-sm">{collection.name}</h3>
          {collection.assets3D === 'Coming Soon' && (
            <span className="text-xs text-amber-600">{collection.assets3D}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
