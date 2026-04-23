// @ts-nocheck
import React, { useEffect, useRef, useState, Suspense, lazy } from 'react';
import { X, Box, ExternalLink, Image, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

const VRMViewer = lazy(() => import('./VRMViewer'));

const AltiiPreviewModal = ({ isOpen, onClose, avatar }) => {
  const closeRef = useRef<HTMLButtonElement>(null);
  const hasVrm = Boolean(avatar?.vrmUrl);
  const [view3D, setView3D] = useState(hasVrm);

  // Reset view mode when avatar changes
  useEffect(() => {
    setView3D(Boolean(avatar?.vrmUrl));
  }, [avatar]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handler);
      document.body.style.overflow = 'hidden';
      closeRef.current?.focus();
    }
    return () => {
      document.removeEventListener('keydown', handler);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="preview-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/90 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl max-h-[90vh] overflow-auto rounded-xl border border-border bg-card shadow-xl animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <Button
          ref={closeRef}
          variant="ghost"
          size="icon"
          className="absolute right-3 top-3 z-10 rounded-full"
          onClick={onClose}
          aria-label="Close preview"
        >
          <X className="size-5" />
        </Button>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr,280px] gap-0">
          <div className="relative aspect-square lg:aspect-auto lg:min-h-[400px] rounded-t-xl lg:rounded-l-xl lg:rounded-tr-none overflow-hidden bg-[#0d0d0d]">
            {view3D && hasVrm ? (
              <Suspense fallback={
                <div className="w-full h-full flex items-center justify-center">
                  <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                </div>
              }>
                <VRMViewer url={avatar.vrmUrl} />
              </Suspense>
            ) : (
              avatar?.image ? (
                <img
                  src={avatar.image}
                  alt={avatar?.name || 'Avatar preview'}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
                  No preview available
                </div>
              )
            )}

            {/* 2D / 3D toggle button */}
            {hasVrm && avatar?.image && (
              <button
                onClick={() => setView3D((v) => !v)}
                className="absolute bottom-3 right-3 z-10 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-black/60 backdrop-blur-md border border-white/10 text-xs font-medium text-white/80 hover:bg-black/80 hover:text-white transition-colors"
                title={view3D ? 'Switch to 2D image' : 'Switch to 3D viewer'}
              >
                {view3D ? (
                  <>
                    <Image className="size-3.5" />
                    2D
                  </>
                ) : (
                  <>
                    <RotateCcw className="size-3.5" />
                    3D
                  </>
                )}
              </button>
            )}
          </div>
          <div className="p-6 flex flex-col gap-4">
            <div>
              <h2 id="preview-modal-title" className="text-xl font-bold text-foreground">{avatar?.name}</h2>
              <p className="text-sm text-muted-foreground">{avatar?.collection}</p>
            </div>
            {avatar?.license && (
              <span className="inline-block text-xs px-2 py-0.5 rounded bg-emerald-600/20 text-emerald-400 w-fit">
                {avatar.license}
              </span>
            )}
            {avatar?.stats && (
              <div>
                <h3 className="font-semibold text-foreground mb-2 text-sm">Stats</h3>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {avatar.stats.triangles && (
                    <div className="px-2 py-1.5 rounded-md bg-muted/50">
                      <div className="text-muted-foreground">Triangles</div>
                      <div className="font-medium text-foreground">{avatar.stats.triangles.toLocaleString()}</div>
                    </div>
                  )}
                  {avatar.stats.fileSize && (
                    <div className="px-2 py-1.5 rounded-md bg-muted/50">
                      <div className="text-muted-foreground">File Size</div>
                      <div className="font-medium text-foreground">
                        {(avatar.stats.fileSize / 1024 / 1024).toFixed(1)} MB
                        {avatar.stats.fileSizeOptimized && (
                          <span className="text-emerald-400 ml-1">
                            → {(avatar.stats.fileSizeOptimized / 1024 / 1024).toFixed(1)} MB
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
            {avatar?.traits && Object.keys(avatar.traits).length > 0 && (
              <div>
                <h3 className="font-semibold text-foreground mb-2 text-sm flex items-center gap-1.5">
                  <Box className="size-3.5" />
                  Traits
                </h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(avatar.traits).map(([k, v]) => (
                    <span
                      key={k}
                      className="text-xs px-2 py-1 rounded-md bg-muted/50 text-foreground"
                    >
                      {k}: {v}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {avatar?.opensea && (
              <div className="mt-auto pt-4">
                <Button asChild className="w-full">
                  <a href={avatar.opensea} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center gap-2">
                    <ExternalLink className="size-4" />
                    View on marketplace
                  </a>
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AltiiPreviewModal;
