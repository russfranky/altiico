/**
 * Full-page loading skeleton displayed while route chunks are loading.
 * Mimics the general page layout (navbar placeholder + content area)
 * to avoid layout shift and blank white screens.
 */
export default function PageSkeleton() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Navbar placeholder */}
      <div className="h-14 border-b border-border bg-background/95 backdrop-blur">
        <div className="flex h-full max-w-7xl mx-auto items-center justify-between px-4">
          <div className="h-5 w-20 rounded bg-muted animate-pulse" />
          <div className="hidden md:flex items-center gap-6">
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
          </div>
          <div className="h-9 w-64 rounded-lg bg-muted animate-pulse hidden sm:block" />
        </div>
      </div>

      {/* Content skeleton */}
      <main className="flex-1 max-w-7xl mx-auto px-4 py-16 w-full">
        <div className="space-y-4 mb-12">
          <div className="h-8 w-64 rounded bg-muted animate-pulse" />
          <div className="h-4 w-96 rounded bg-muted/60 animate-pulse" />
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card overflow-hidden">
              <div className="aspect-video bg-muted animate-pulse" />
              <div className="p-4 space-y-3">
                <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
                <div className="h-3 w-1/2 rounded bg-muted/60 animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
