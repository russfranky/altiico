import React from 'react';
import { cn } from '@/lib/utils';

/** Skeleton placeholder for avatar grid cards */
const AvatarCardSkeleton = ({ className }: { className?: string }) => (
  <div
    className={cn(
      'rounded-lg border border-border bg-card overflow-hidden',
      className
    )}
  >
    <div className="aspect-square bg-muted/50 animate-pulse" />
    <div className="p-2 sm:p-2.5 space-y-2">
      <div className="h-3 w-8 bg-muted/60 rounded animate-pulse" />
      <div className="h-3 w-20 bg-muted/40 rounded animate-pulse" />
      <div className="flex gap-2">
        <div className="h-3 w-12 bg-muted/40 rounded animate-pulse" />
        <div className="h-3 w-10 bg-muted/40 rounded animate-pulse" />
      </div>
    </div>
  </div>
);

export default AvatarCardSkeleton;
