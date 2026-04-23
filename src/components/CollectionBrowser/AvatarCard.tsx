// Cherry-picked from hubzz-altiico/src/components/CollectionBrowser/AvatarCard.tsx
// Adjusted: uses ApiAvatar (live API type). Removed static-data specific fields
// (opensea link, price, contract etherscan link — not in API response).

import React from 'react';
import type { AvatarCardProps } from './types';

const PLACEHOLDER = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJzYW5zLXNlcmlmIiBmb250LXNpemU9IjE0IiBmaWxsPSIjZmZmIj5ObyBJbWFnZTwvdGV4dD48L3N2Zz4=';

const AvatarCard: React.FC<AvatarCardProps> = ({ avatar, mode, onPreview, onSelect }) => {
  const handleImgError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.src = PLACEHOLDER;
  };

  const hasVrm = !!(avatar.optimized_vrm_url ?? avatar.original_vrm_url);

  return (
    <article className="group rounded-lg border border-border bg-card overflow-hidden hover:border-primary/50 hover:shadow-md transition-all">
      <button
        type="button"
        onClick={() => mode === 'select' && onSelect ? onSelect(avatar) : onPreview(avatar)}
        className="block w-full text-left"
      >
        <div className="aspect-square relative bg-muted/30 overflow-hidden cursor-pointer">
          <img
            src={avatar.thumbnail_url || avatar.image_url || PLACEHOLDER}
            alt={avatar.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            onError={handleImgError}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          <div className="absolute top-2 left-2 flex gap-1 flex-wrap">
            {hasVrm && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-primary/80 text-primary-foreground">
                VRM
              </span>
            )}
          </div>
          {mode === 'select' && (
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
              <span className="text-white text-sm font-semibold px-4 py-2 rounded-lg bg-primary/90">
                Select
              </span>
            </div>
          )}
        </div>
      </button>

      <div className="p-2 sm:p-2.5">
        <div className="text-xs font-semibold text-foreground truncate">#{avatar.token_id}</div>
        <div className="text-[11px] text-muted-foreground truncate mt-0.5">{avatar.name}</div>
        {mode === 'browse' && (
          <button
            type="button"
            onClick={() => onPreview(avatar)}
            className="mt-1.5 text-[11px] text-primary hover:underline"
          >
            Preview
          </button>
        )}
        {mode === 'select' && (
          <button
            type="button"
            onClick={() => onSelect?.(avatar)}
            className="mt-1.5 text-[11px] text-primary hover:underline"
          >
            Use this avatar
          </button>
        )}
      </div>
    </article>
  );
};

export default AvatarCard;
