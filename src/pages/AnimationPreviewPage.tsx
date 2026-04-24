import React, { lazy, Suspense, useEffect, useState, useRef, useCallback } from 'react';
import type { IsometricCanvasHandle } from '@/components/IsometricCanvas';
import type { DragOffset } from '@/components/AvatarDragHandles';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from '@/components/ui/dialog';
import { CollectionBrowser } from '@/components/CollectionBrowser';
import { API_BASE_URL } from '@/config/api';
import type { ApiCollection, ApiAvatar } from '@/lib/avatarApiTypes';
import { getVrmUrl } from '@/lib/avatarApiTypes';
import type { PropDefinition, PropInstance, PropManifest } from '@/lib/propsTypes';
import { HUBZZ_SEAT_HEIGHTS, AVATAR_TARGET_HEIGHT_MIN, AVATAR_TARGET_HEIGHT_MAX } from '@/hooks/useHubzzCamera';
import type { SeatHeightStandard } from '@/hooks/useHubzzCamera';
import { makeEntry, exportSession, resolveEffectiveOffset } from '@/lib/rigCorrection';
import type { RigCorrectionEntry, RigCorrectionScope } from '@/lib/rigCorrection';
import { buildCollectionManifest, downloadManifest, collectionsTouchedBySession } from '@/lib/manifest';
import { renderPfpThumbnail } from '@/lib/pfpThumbnailRenderer';
import { uploadPfpThumbnail } from '@/services/pfpUploadService';
import { usePrivy } from '@privy-io/react-auth';
import { Play, Pause, RotateCcw, Upload } from 'lucide-react';
import * as THREE from 'three';
import type { VRM } from '@pixiv/three-vrm';

// Lazy load IsometricCanvas — three.js is heavy (~560KB). The page renders
// the full layout immediately; the canvas loads asynchronously.
const IsometricCanvas = lazy(() => import('@/components/IsometricCanvas'));

// Feature flag — props/furniture are hidden from the rig-QA preview to keep
// focus on avatar rigging. When the Assets tab is built, flip this or move
// the prop UI there. All prop code is preserved; only the UI is gated.
const SHOW_PROPS = false;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AnimationEntry {
  id: string;
  name: string;
  url: string;
  category: string;
  /** 'mixamo' (FBX, default) or 'ual' (Quaternius GLB library). */
  source?: 'mixamo' | 'ual';
  /** For source='ual' — the clip name inside the shared GLB. */
  clipName?: string;
}

interface AnimationManifest {
  animations: AnimationEntry[];
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

function useCollections() {
  const [collections, setCollections] = useState<ApiCollection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE_URL}/collections`)
      .then((r) => r.json())
      .then((data: { collections: ApiCollection[] }) => {
        // Filter to staged + published only (QA-relevant states)
        const visible = data.collections.filter(
          (c) => c.status === 'published' || c.status === 'staged'
        );
        setCollections(visible);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return { collections, loading };
}

function useAvatars(collectionSlug: string | null) {
  const [avatars, setAvatars] = useState<ApiAvatar[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!collectionSlug) {
      setAvatars([]);
      return;
    }
    setLoading(true);
    fetch(`${API_BASE_URL}/avatars?collection=${collectionSlug}&limit=100`)
      .then((r) => r.json())
      .then((data: { avatars: ApiAvatar[] }) => setAvatars(data.avatars ?? []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [collectionSlug]);

  return { avatars, loading };
}

function useAnimationManifest() {
  const [animations, setAnimations] = useState<AnimationEntry[]>([]);

  useEffect(() => {
    fetch('/animations.json')
      .then((r) => r.json())
      .then((data: AnimationManifest) => setAnimations(data.animations ?? []))
      .catch(console.error);
  }, []);

  return animations;
}

function usePropsManifest() {
  const [props, setProps] = useState<PropDefinition[]>([]);

  useEffect(() => {
    fetch('/props.json')
      .then((r) => r.json())
      .then((data: PropManifest) => setProps(data.props ?? []))
      .catch(console.error);
  }, []);

  return props;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function LeftColumn({
  collections,
  collectionsLoading,
  selectedCollectionSlug,
  onSelectCollection,
  avatars,
  avatarsLoading,
  selectedAvatar,
  onSelectAvatar,
  onUploadVrm,
}: {
  collections: ApiCollection[];
  collectionsLoading: boolean;
  selectedCollectionSlug: string | null;
  onSelectCollection: (slug: string) => void;
  avatars: ApiAvatar[];
  avatarsLoading: boolean;
  selectedAvatar: ApiAvatar | null;
  onSelectAvatar: (avatar: ApiAvatar) => void;
  onUploadVrm: (url: string) => void;
}) {
  const dropRef = useRef<HTMLDivElement>(null);

  const handleVrmFileUpload = (file: File) => {
    const objectUrl = URL.createObjectURL(file);
    onUploadVrm(objectUrl);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith('.vrm') || file.name.endsWith('.glb'))) {
      handleVrmFileUpload(file);
    }
  };

  return (
    <div className="flex flex-col gap-3 h-full overflow-hidden">
      {/* Collection picker */}
      <div>
        <Label className="text-xs text-muted-foreground uppercase tracking-wider mb-1 block">
          Collection
        </Label>
        <Select
          value={selectedCollectionSlug ?? ''}
          onValueChange={onSelectCollection}
          disabled={collectionsLoading}
        >
          <SelectTrigger className="h-8 text-xs">
            <SelectValue placeholder={collectionsLoading ? 'Loading...' : 'Pick an avatar set'} />
          </SelectTrigger>
          <SelectContent>
            {collections.map((c) => (
              <SelectItem key={c.slug} value={c.slug}>
                {c.name}
                {c.status === 'staged' && (
                  <span className="ml-1 text-[10px] text-amber-400">[staged]</span>
                )}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Avatar grid */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {selectedCollectionSlug ? (
          <CollectionBrowser
            mode="select"
            avatars={avatars}
            loading={avatarsLoading}
            onSelect={onSelectAvatar}
            onPreview={onSelectAvatar}
            itemsPerPage={20}
            emptyMessage="No VRM-ready avatars in this collection."
          />
        ) : (
          <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
            Select a collection above
          </div>
        )}
      </div>

      {/* VRM upload — modal-gated for cleaner UI */}
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 text-xs gap-2">
            <Upload className="size-3.5" />
            Upload VRM
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload VRM</DialogTitle>
            <DialogDescription>
              Test a VRM in altiico without committing it upstream. Session-only — not persisted.
            </DialogDescription>
          </DialogHeader>
          <div
            ref={dropRef}
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-border rounded-lg p-8 text-center text-sm text-muted-foreground hover:border-primary/50 transition-colors cursor-pointer"
          >
            <label className="cursor-pointer flex flex-col items-center gap-2">
              <Upload className="size-8 opacity-60" />
              <span className="font-medium">Drop VRM or click to browse</span>
              <span className="text-xs text-muted-foreground/60">.vrm or .glb — up to ~100MB</span>
              <input
                type="file"
                accept=".vrm,.glb"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleVrmFileUpload(file);
                }}
              />
            </label>
          </div>
        </DialogContent>
      </Dialog>

      {/* Selected avatar indicator */}
      {selectedAvatar && (
        <Card className="p-2">
          <div className="flex items-center gap-2">
            <img
              src={selectedAvatar.thumbnail_url}
              alt={selectedAvatar.name}
              className="size-8 rounded object-cover"
            />
            <div className="min-w-0">
              <div className="text-xs font-medium truncate">{selectedAvatar.name}</div>
              <div className="text-[10px] text-muted-foreground truncate">{selectedAvatar.collection_name}</div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function RightColumn({
  animations,
  selectedAnimId,
  onSelectAnim,
  isPlaying,
  onTogglePlay,
  loop,
  onToggleLoop,
  speed,
  onSpeedChange,
  onResetCamera,
  showBones,
  onToggleBones,
  showBounds,
  onToggleBounds,
  onUploadFbx,
  propDefinitions,
  activeProps,
  onToggleProp,
  onUpdateProp,
  dragEnabled,
  onToggleDrag,
  dragOffset,
  dragClamped,
  onResetDragOffset,
  onSaveToSession,
  onExportSession,
  onExportManifest,
  onCaptureFbThumbnail,
  onBatchRenderPfp,
  onBatchStop,
  batchStatus,
  sessionCount,
  rigScope,
  onScopeSwitch,
  scopeSwitchPrompt,
  onScopeSwitchTransfer,
  onScopeSwitchDiscard,
  onScopeSwitchCancel,
  resolvedCorrection,
  avatarSessionCount,
  collectionSessionCount,
  selectedCollectionName,
  seatHeight,
  onSeatHeightChange,
  avatarFacingDeg,
  onAvatarFacingDegChange,
  offsetClearedNotice,
  sessionNotice,
}: {
  animations: AnimationEntry[];
  selectedAnimId: string | null;
  onSelectAnim: (id: string) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  loop: boolean;
  onToggleLoop: (v: boolean) => void;
  speed: number;
  onSpeedChange: (v: number) => void;
  onResetCamera: () => void;
  showBones: boolean;
  onToggleBones: (v: boolean) => void;
  showBounds: boolean;
  onToggleBounds: (v: boolean) => void;
  onUploadFbx: (url: string, name: string) => void;
  propDefinitions: PropDefinition[];
  activeProps: Record<string, PropInstance>;
  onToggleProp: (def: PropDefinition) => void;
  onUpdateProp: (id: string, partial: Partial<Omit<PropInstance, 'definition'>>) => void;
  dragEnabled: boolean;
  onToggleDrag: (v: boolean) => void;
  dragOffset: DragOffset;
  dragClamped: boolean;
  onResetDragOffset: () => void;
  onSaveToSession: () => void;
  onExportSession: () => void;
  onExportManifest: () => void;
  onCaptureFbThumbnail: () => void;
  onBatchRenderPfp: () => void;
  onBatchStop: () => void;
  batchStatus: {
    running: boolean;
    done: number;
    total: number;
    failed: number;
    stop: boolean;
    lastError: string | null;
  };
  sessionCount: number;
  rigScope: RigCorrectionScope;
  onScopeSwitch: (v: RigCorrectionScope) => void;
  scopeSwitchPrompt: RigCorrectionScope | null;
  onScopeSwitchTransfer: () => void;
  onScopeSwitchDiscard: () => void;
  onScopeSwitchCancel: () => void;
  resolvedCorrection: {
    offset: { x: number; y: number; z: number };
    source: 'default' | 'collection' | 'avatar';
    collectionEntry: RigCorrectionEntry | null;
    avatarEntry: RigCorrectionEntry | null;
  } | null;
  avatarSessionCount: number;
  collectionSessionCount: number;
  selectedCollectionName: string | null;
  seatHeight: SeatHeightStandard;
  onSeatHeightChange: (v: SeatHeightStandard) => void;
  avatarFacingDeg: number;
  onAvatarFacingDegChange: (deg: number) => void;
  offsetClearedNotice: boolean;
  sessionNotice: { tone: 'error' | 'info'; msg: string } | null;
}) {
  const byCategory = animations.reduce<Record<string, AnimationEntry[]>>((acc, a) => {
    (acc[a.category] ??= []).push(a);
    return acc;
  }, {});

  const handleFbxUpload = (file: File) => {
    const url = URL.createObjectURL(file);
    onUploadFbx(url, file.name.replace(/\.fbx$/i, ''));
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <Tabs defaultValue="animation" className="flex flex-col h-full">
        <TabsList className="w-full grid grid-cols-3 shrink-0">
          <TabsTrigger value="animation" className="text-xs">Animation</TabsTrigger>
          <TabsTrigger value="rigging" className="text-xs">Rigging</TabsTrigger>
          <TabsTrigger value="scene" className="text-xs">Scene</TabsTrigger>
        </TabsList>

        <TabsContent value="animation" className="flex flex-col gap-4 overflow-y-auto flex-1 mt-3">
      {/* Animation picker */}
      <div>
        <Label className="text-xs text-muted-foreground uppercase tracking-wider mb-1 block">
          Animation
        </Label>
        <Select
          value={selectedAnimId ?? ''}
          onValueChange={onSelectAnim}
          disabled={animations.length === 0}
        >
          <SelectTrigger className="h-8 text-xs">
            <SelectValue placeholder={animations.length === 0 ? 'No animations' : 'Pick animation'} />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(byCategory).map(([cat, anims]) => (
              <React.Fragment key={cat}>
                <div className="px-2 py-1 text-[10px] text-muted-foreground uppercase tracking-wider">
                  {cat}
                </div>
                {anims.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.name}
                  </SelectItem>
                ))}
              </React.Fragment>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Transport controls */}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant={isPlaying ? 'outline' : 'default'}
          className="h-8 flex-1"
          onClick={onTogglePlay}
        >
          {isPlaying ? <Pause className="size-3.5 mr-1" /> : <Play className="size-3.5 mr-1" />}
          {isPlaying ? 'Pause' : 'Play'}
        </Button>
        <Button
          size="icon"
          variant="outline"
          className="h-8 w-8"
          onClick={onResetCamera}
          title="Reset camera"
        >
          <RotateCcw className="size-3.5" />
        </Button>
      </div>

      {/* Loop toggle */}
      <div className="flex items-center justify-between">
        <Label className="text-xs">Loop</Label>
        <Switch checked={loop} onCheckedChange={onToggleLoop} />
      </div>

      {/* Speed slider */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <Label className="text-xs">Speed</Label>
          <span className="text-xs text-muted-foreground">{speed.toFixed(1)}x</span>
        </div>
        <Slider
          min={10}
          max={200}
          step={10}
          value={[Math.round(speed * 100)]}
          onValueChange={([v]) => onSpeedChange(v / 100)}
        />
      </div>

      {/* FBX upload — modal-gated */}
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 text-xs gap-2 w-full">
            <Upload className="size-3.5" />
            Upload FBX
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload FBX</DialogTitle>
            <DialogDescription>
              Test an unpublished animation on the current avatar. Session-only — not persisted.
            </DialogDescription>
          </DialogHeader>
          <div
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files[0];
              if (file?.name.endsWith('.fbx')) handleFbxUpload(file);
            }}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-border rounded-lg p-8 text-center text-sm text-muted-foreground hover:border-primary/50 transition-colors cursor-pointer"
          >
            <label className="cursor-pointer flex flex-col items-center gap-2">
              <Upload className="size-8 opacity-60" />
              <span className="font-medium">Drop FBX or click to browse</span>
              <span className="text-xs text-muted-foreground/60">Mixamo-style skeletal animation</span>
              <input
                type="file"
                accept=".fbx"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFbxUpload(file);
                }}
              />
            </label>
          </div>
        </DialogContent>
      </Dialog>

      {/* FB thumbnail capture — renders the current canvas pose to a PNG download.
          Use with anim_idle for canonical collection thumbnails. */}
      <Button
        variant="outline"
        size="sm"
        className="h-8 text-xs gap-2 w-full"
        onClick={onCaptureFbThumbnail}
      >
        Capture FB thumbnail
      </Button>

      {/* Overlay toggles */}
      <Card className="p-3 space-y-2">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Overlays
        </div>
        <div className="flex items-center justify-between">
          <Label className="text-xs">Bones</Label>
          <Switch checked={showBones} onCheckedChange={onToggleBones} />
        </div>
        <div className="flex items-center justify-between">
          <Label className="text-xs">1x1 Tile bounds</Label>
          <Switch checked={showBounds} onCheckedChange={onToggleBounds} />
        </div>
      </Card>

        </TabsContent>

        <TabsContent value="rigging" className="flex flex-col gap-4 overflow-y-auto flex-1 mt-3">
      {/* Rig correction — drag-to-adjust */}
      <Card className={`p-3 space-y-2 ${dragClamped && dragEnabled ? 'ring-1 ring-red-500/60' : ''}`}>
        <div className="flex items-center justify-between">
          <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Rig correction
          </Label>
          <Switch checked={dragEnabled} onCheckedChange={onToggleDrag} />
        </div>

        {/* Current correction readout — always visible when an avatar is loaded */}
        {resolvedCorrection && (
          <div className="text-[10px] space-y-0.5 border-l-2 pl-2 py-0.5"
               style={{
                 borderColor:
                   resolvedCorrection.source === 'avatar' ? 'rgb(var(--primary-rgb, 99 102 241))' :
                   resolvedCorrection.source === 'collection' ? 'rgb(156 163 175)' :
                   'rgb(75 85 99)',
               }}>
            <div className="text-muted-foreground uppercase tracking-wider text-[9px]">Current correction</div>
            {resolvedCorrection.source === 'default' && (
              <div className="text-muted-foreground">Default (no correction)</div>
            )}
            {resolvedCorrection.collectionEntry && (
              <div className={resolvedCorrection.source === 'avatar' ? 'text-muted-foreground/70 line-through' : 'text-muted-foreground'}>
                Collection: ΔX{resolvedCorrection.collectionEntry.offset.x.toFixed(2)} ΔY{resolvedCorrection.collectionEntry.offset.y.toFixed(2)} ΔZ{resolvedCorrection.collectionEntry.offset.z.toFixed(2)}
              </div>
            )}
            {resolvedCorrection.avatarEntry && (
              <div className="text-primary">
                Per-avatar: ΔX{resolvedCorrection.avatarEntry.offset.x.toFixed(2)} ΔY{resolvedCorrection.avatarEntry.offset.y.toFixed(2)} ΔZ{resolvedCorrection.avatarEntry.offset.z.toFixed(2)}
              </div>
            )}
          </div>
        )}

        {dragEnabled && (
          <>
            {/* Scope toggle — shadcn ToggleGroup */}
            <ToggleGroup
              type="single"
              size="sm"
              variant="outline"
              value={rigScope}
              onValueChange={(v) => v && onScopeSwitch(v as RigCorrectionScope)}
              className="w-full"
            >
              <ToggleGroupItem value="avatar" className="text-[11px]">
                Avatar
              </ToggleGroupItem>
              <ToggleGroupItem
                value="collection"
                className="text-[11px]"
                title={selectedCollectionName ? `Applies to entire ${selectedCollectionName} set` : undefined}
              >
                Set
              </ToggleGroupItem>
            </ToggleGroup>

            {/* Scope hint */}
            <div className="text-[10px] text-muted-foreground">
              {rigScope === 'avatar'
                ? 'Correction applies to this avatar only.'
                : selectedCollectionName
                  ? `Correction applies to all avatars in ${selectedCollectionName}.`
                  : 'Correction applies to the entire collection.'}
            </div>

            {/* Conflict warning */}
            {rigScope === 'avatar' && resolvedCorrection?.collectionEntry && (
              <div className="text-[10px] text-amber-400">
                Overrides collection default (ΔY {resolvedCorrection.collectionEntry.offset.y.toFixed(2)}).
              </div>
            )}

            <div className="text-[10px] text-muted-foreground">
              Drag to nudge.{' '}
              <kbd className="px-1 bg-muted rounded text-[9px]">Shift</kbd> = Y only.{' '}
              <kbd className="px-1 bg-muted rounded text-[9px]">Ctrl</kbd> = ground plane only.
            </div>
            {offsetClearedNotice && (
              <div className="text-[10px] text-amber-400">
                Offset cleared — context changed.
              </div>
            )}
            <div className="grid grid-cols-3 gap-1 font-mono text-[11px]">
              <div className={`rounded px-1.5 py-0.5 ${Math.abs(dragOffset.x) >= 0.5 ? 'bg-red-900/40 text-red-300' : 'bg-muted'}`}>
                <span className="text-muted-foreground">ΔX</span> {dragOffset.x.toFixed(3)}
              </div>
              <div className={`rounded px-1.5 py-0.5 ${Math.abs(dragOffset.y) >= 0.5 ? 'bg-red-900/40 text-red-300' : 'bg-muted'}`}>
                <span className="text-muted-foreground">ΔY</span> {dragOffset.y.toFixed(3)}
              </div>
              <div className={`rounded px-1.5 py-0.5 ${Math.abs(dragOffset.z) >= 0.5 ? 'bg-red-900/40 text-red-300' : 'bg-muted'}`}>
                <span className="text-muted-foreground">ΔZ</span> {dragOffset.z.toFixed(3)}
              </div>
            </div>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-[11px] flex-1"
                onClick={onResetDragOffset}
              >
                Reset
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-[11px] flex-1"
                onClick={onSaveToSession}
              >
                Save as {rigScope}
              </Button>
            </div>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-[11px] flex-1"
                onClick={onExportSession}
                disabled={sessionCount === 0}
                title={sessionCount === 0 ? 'No entries yet — save at least one first' : `Raw session JSON (audit/debug). ${collectionSessionCount}c + ${avatarSessionCount}a.`}
              >
                Export raw ({sessionCount})
              </Button>
              <Button
                size="sm"
                variant={sessionCount > 0 ? 'default' : 'outline'}
                className="h-7 text-[11px] flex-1"
                onClick={onExportManifest}
                disabled={sessionCount === 0}
                title={sessionCount === 0 ? 'No entries yet — save at least one first' : 'One JSON per avatar set, cascade pre-resolved, ready for hubzz'}
              >
                Export manifests
              </Button>
            </div>
            <div className="flex gap-1 pt-1 border-t border-border mt-1">
              <Button
                size="sm"
                variant={batchStatus.running ? 'destructive' : 'default'}
                className="h-7 text-[11px] flex-1"
                onClick={batchStatus.running ? onBatchStop : onBatchRenderPfp}
                title="Render pfp thumbnails for every avatar in the current collection and upload to R2. Rendered URLs are spliced into the next manifest export."
              >
                {batchStatus.running
                  ? `Stop (${batchStatus.done}/${batchStatus.total})`
                  : 'Batch pfp → R2'}
              </Button>
            </div>
            {batchStatus.total > 0 && !batchStatus.running && (
              <div className="text-[10px] text-muted-foreground">
                pfp batch: {batchStatus.done - batchStatus.failed}/{batchStatus.total} ok
                {batchStatus.failed > 0 && <span className="text-red-400"> · {batchStatus.failed} failed</span>}
                {batchStatus.lastError && <div className="text-red-400 truncate" title={batchStatus.lastError}>last: {batchStatus.lastError}</div>}
              </div>
            )}
            {batchStatus.running && batchStatus.total > 0 && (
              <div className="text-[10px] text-muted-foreground">
                rendering {batchStatus.done}/{batchStatus.total}
                {batchStatus.failed > 0 && <span className="text-red-400"> · {batchStatus.failed} failed</span>}
              </div>
            )}
            {sessionNotice && (
              <div
                className={`text-[10px] ${
                  sessionNotice.tone === 'error' ? 'text-red-400' : 'text-emerald-400'
                }`}
                role="status"
              >
                {sessionNotice.msg}
              </div>
            )}
          </>
        )}

      </Card>
        </TabsContent>

      {/* Scope switch confirmation — decision C. Outside all Tabs so it can fire regardless of which tab is active. */}
      <AlertDialog
        open={scopeSwitchPrompt !== null}
        onOpenChange={(open) => !open && onScopeSwitchCancel()}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Switch to {scopeSwitchPrompt} scope?</AlertDialogTitle>
            <AlertDialogDescription>
              You have an unsaved offset:{' '}
              <span className="font-mono text-foreground">
                ΔX {dragOffset.x.toFixed(2)} ΔY {dragOffset.y.toFixed(2)} ΔZ {dragOffset.z.toFixed(2)}
              </span>
              .{' '}
              {scopeSwitchPrompt === 'collection' ? (
                <>
                  Applying this at <strong>set</strong> scope will affect every avatar in{' '}
                  <strong>{selectedCollectionName ?? 'this avatar set'}</strong>.
                </>
              ) : (
                <>Applying this at <strong>avatar</strong> scope will affect only the current avatar.</>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={onScopeSwitchCancel}>Cancel</AlertDialogCancel>
            <Button variant="outline" onClick={onScopeSwitchDiscard}>
              Discard offset
            </Button>
            <AlertDialogAction onClick={onScopeSwitchTransfer}>
              Transfer to {scopeSwitchPrompt}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

        <TabsContent value="scene" className="flex flex-col gap-4 overflow-y-auto flex-1 mt-3">
      {/* Seat height + facing */}
      <Card className="p-3 space-y-3">
        <div>
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
            Seat height
          </div>
          <div className="grid grid-cols-2 gap-1">
            {(['none', 'floor', 'chair', 'stool'] as const).map((key) => {
              const label =
                key === 'none' ? 'Standing' :
                `${key[0].toUpperCase()}${key.slice(1)} ${HUBZZ_SEAT_HEIGHTS[key as keyof typeof HUBZZ_SEAT_HEIGHTS].toFixed(2)}m`;
              return (
                <Button
                  key={key}
                  size="sm"
                  variant={seatHeight === key ? 'default' : 'outline'}
                  className="h-7 text-[11px] px-2"
                  onClick={() => onSeatHeightChange(key)}
                >
                  {label}
                </Button>
              );
            })}
          </div>
        </div>
        <div>
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
            Facing (sitTarget)
          </div>
          <div className="grid grid-cols-4 gap-1">
            {[0, 90, 180, 270].map((deg) => (
              <Button
                key={deg}
                size="sm"
                variant={avatarFacingDeg === deg ? 'default' : 'outline'}
                className="h-7 text-[11px] px-1"
                onClick={() => onAvatarFacingDegChange(deg)}
                title={
                  deg === 0 ? 'Facing camera' :
                  deg === 90 ? 'Facing avatar-right' :
                  deg === 180 ? 'Facing away from camera' :
                  'Facing avatar-left'
                }
              >
                {deg}
              </Button>
            ))}
          </div>
        </div>
      </Card>

      {/* Props — hidden from rig-QA preview (see SHOW_PROPS flag). Will move to Assets tab. */}
      {SHOW_PROPS && propDefinitions.length > 0 && (
        <Card className="p-3 space-y-2">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Props
          </div>
          {propDefinitions.map((def) => {
            const inst = activeProps[def.id];
            const active = Boolean(inst);
            return (
              <div key={def.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">{def.name}</Label>
                  <Switch checked={active} onCheckedChange={() => onToggleProp(def)} />
                </div>
                {active && inst && (
                  <div className="pl-2 space-y-1.5 border-l border-border/50">
                    <div className="flex items-center justify-between gap-2">
                      <Label className="text-[10px] text-muted-foreground w-8">X tile</Label>
                      <Input
                        type="number"
                        step="1"
                        value={inst.offset.x}
                        onChange={(e) => onUpdateProp(def.id, { offset: { ...inst.offset, x: Math.round(parseFloat(e.target.value) || 0) } })}
                        className="h-6 flex-1 text-xs"
                      />
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <Label className="text-[10px] text-muted-foreground w-8">Z tile</Label>
                      <Input
                        type="number"
                        step="1"
                        value={inst.offset.z}
                        onChange={(e) => onUpdateProp(def.id, { offset: { ...inst.offset, z: Math.round(parseFloat(e.target.value) || 0) } })}
                        className="h-6 flex-1 text-xs"
                      />
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <Label className="text-[10px] text-muted-foreground w-8">Rot</Label>
                      <Input
                        type="number"
                        step="45"
                        value={Math.round((inst.rotY * 180) / Math.PI)}
                        onChange={(e) => {
                          const deg = Math.round((parseFloat(e.target.value) || 0) / 45) * 45;
                          onUpdateProp(def.id, { rotY: (deg * Math.PI) / 180 });
                        }}
                        className="h-6 flex-1 text-xs"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </Card>
      )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AnimationPreviewPage() {
  const { collections, loading: collectionsLoading } = useCollections();
  const [selectedCollectionSlug, setSelectedCollectionSlug] = useState<string | null>(null);
  const { avatars, loading: avatarsLoading } = useAvatars(selectedCollectionSlug);
  const animations = useAnimationManifest();
  const propDefinitions = usePropsManifest();

  // Per-collection avatar cache — needed at manifest-export time to merge rig
  // corrections with full metadata. Populated lazily as the user visits collections.
  const [collectionAvatarsCache, setCollectionAvatarsCache] = useState<Record<string, ApiAvatar[]>>({});
  useEffect(() => {
    if (selectedCollectionSlug && avatars.length > 0) {
      setCollectionAvatarsCache((prev) =>
        prev[selectedCollectionSlug] ? prev : { ...prev, [selectedCollectionSlug]: avatars }
      );
    }
  }, [selectedCollectionSlug, avatars]);

  // Active props: map from propId -> PropInstance (with per-instance offset overrides)
  const [activeProps, setActiveProps] = useState<Record<string, PropInstance>>({});

  const togglePropActive = (def: PropDefinition) => {
    setActiveProps((prev) => {
      if (prev[def.id]) {
        const next = { ...prev };
        delete next[def.id];
        return next;
      }
      // Inherit the active seat height as prop Y — mirrors hubzz editor behavior
      // where sittable assets are placed at the tile's seatHeight
      const yFromSeat = seatHeight === 'none' ? 0 : HUBZZ_SEAT_HEIGHTS[seatHeight];
      return {
        ...prev,
        [def.id]: {
          definition: def,
          offset: { ...def.defaultOffset, y: yFromSeat },
          rotY: def.defaultRotY,
        },
      };
    });
  };

  const updatePropInstance = (id: string, partial: Partial<Omit<PropInstance, 'definition'>>) => {
    setActiveProps((prev) => {
      const existing = prev[id];
      if (!existing) return prev;
      return {
        ...prev,
        [id]: { ...existing, ...partial, offset: { ...existing.offset, ...(partial.offset ?? {}) } },
      };
    });
  };

  const propInstancesList = Object.values(activeProps);

  // Active avatar VRM URL (from collection pick or drag-drop upload)
  const [activeVrmUrl, setActiveVrmUrl] = useState<string | null>(null);
  const [selectedAvatar, setSelectedAvatar] = useState<ApiAvatar | null>(null);

  // Active FBX animation URL (from manifest pick or drag-drop upload)
  const [selectedAnimId, setSelectedAnimId] = useState<string | null>(null);
  const [activeFbxUrl, setActiveFbxUrl] = useState<string | null>(null);
  // UAL (Quaternius) clip spec — when set, IsometricCanvas uses the GLB loader.
  const [activeUalClip, setActiveUalClip] = useState<{ url: string; clipName: string } | null>(null);

  // Playback state
  const [isPlaying, setIsPlaying] = useState(true);
  const [loop, setLoop] = useState(true);
  const [speed, setSpeed] = useState(1.0);

  // Overlay state
  const [showBones, setShowBones] = useState(false);
  const [showBounds, setShowBounds] = useState(false);

  // Seat height — matches hubzz WorldTile seatHeight standards
  const [seatHeight, setSeatHeight] = useState<SeatHeightStandard>('none');

  // Avatar facing angle — hubzz sitTarget equivalent. 0 = camera-facing (default).
  const [avatarFacingDeg, setAvatarFacingDeg] = useState(0);

  // Measured avatar height after scale chain — for QA vs 1.5–1.75m target band
  const [measuredHeight, setMeasuredHeight] = useState<number | null>(null);

  // Rig correction state
  const [dragEnabled, setDragEnabled] = useState(false);
  const [dragOffset, setDragOffset] = useState<DragOffset>({ x: 0, y: 0, z: 0 });
  const [dragClamped, setDragClamped] = useState(false);

  // Scope toggle — determines whether Save to session creates a per-avatar or
  // per-collection entry. See NORTH_STAR.md rig correction scope section.
  const [rigScope, setRigScope] = useState<'avatar' | 'collection'>('avatar');

  // Prompt state for scope switches with unsaved offset (decision C)
  const [scopeSwitchPrompt, setScopeSwitchPrompt] = useState<'avatar' | 'collection' | null>(null);

  // Session entries — accumulate via "Save to session"
  const [sessionEntries, setSessionEntries] = useState<RigCorrectionEntry[]>([]);

  // Subtle notice: shown briefly when offset is auto-cleared due to context change
  const [offsetClearedNotice, setOffsetClearedNotice] = useState(false);
  const clearNoticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Previous context values for change detection
  const prevContextRef = useRef({
    vrmUrl: null as string | null,
    animId: null as string | null,
    seatHeight: 'none' as SeatHeightStandard,
    facingDeg: 0,
  });

  // Clear offset when context changes (decision #3 — facing, seat, anim, avatar)
  const clearOffsetOnContextChange = useCallback(() => {
    setDragOffset({ x: 0, y: 0, z: 0 });
    setDragClamped(false);
    setOffsetClearedNotice(true);
    if (clearNoticeTimerRef.current) clearTimeout(clearNoticeTimerRef.current);
    clearNoticeTimerRef.current = setTimeout(() => setOffsetClearedNotice(false), 3000);
  }, []);

  // Watch for context changes and fire clear
  useEffect(() => {
    const prev = prevContextRef.current;
    const changed =
      prev.vrmUrl !== activeVrmUrl ||
      prev.animId !== selectedAnimId ||
      prev.seatHeight !== seatHeight ||
      prev.facingDeg !== avatarFacingDeg;

    if (changed) {
      // Only show notice if there was a non-zero offset to clear
      const hadOffset = dragOffset.x !== 0 || dragOffset.y !== 0 || dragOffset.z !== 0;
      if (hadOffset) {
        clearOffsetOnContextChange();
      } else {
        setDragOffset({ x: 0, y: 0, z: 0 });
        setDragClamped(false);
      }
      prevContextRef.current = {
        vrmUrl: activeVrmUrl,
        animId: selectedAnimId,
        seatHeight,
        facingDeg: avatarFacingDeg,
      };
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeVrmUrl, selectedAnimId, seatHeight, avatarFacingDeg]);

  // Cleanup notice timer on unmount
  useEffect(() => {
    return () => {
      if (clearNoticeTimerRef.current) clearTimeout(clearNoticeTimerRef.current);
    };
  }, []);

  const handleVrmLoaded = (vrm: VRM) => {
    // Wait a frame so scale chain has been applied before measuring
    requestAnimationFrame(() => {
      const bbox = new THREE.Box3().setFromObject(vrm.scene);
      const size = new THREE.Vector3();
      bbox.getSize(size);
      setMeasuredHeight(size.y);
    });
  };

  // Canvas imperative reset ref
  const canvasRef = useRef<IsometricCanvasHandle>(null);

  const handleSelectAvatar = (avatar: ApiAvatar) => {
    setSelectedAvatar(avatar);
    setMeasuredHeight(null);
    const url = getVrmUrl(avatar);
    setActiveVrmUrl(url);
  };

  const handleUploadVrm = (url: string) => {
    setSelectedAvatar(null);
    setMeasuredHeight(null);
    setActiveVrmUrl(url);
  };

  const handleSelectAnim = (id: string) => {
    setSelectedAnimId(id);
    const entry = animations.find((a) => a.id === id);
    if (!entry) return;
    if (entry.source === 'ual' && entry.clipName) {
      setActiveFbxUrl(null);
      setActiveUalClip({ url: entry.url, clipName: entry.clipName });
    } else {
      setActiveUalClip(null);
      setActiveFbxUrl(entry.url);
    }

    // Auto-sync seat state with animation type.
    // Sit animations default to chair height (most common test case); all other
    // animation categories reset to standing. User can override the seat pick
    // afterward without affecting the animation.
    const isSitAnim = entry.id.startsWith('anim_sit') || entry.name.toLowerCase().includes('sit');
    if (isSitAnim && seatHeight === 'none') {
      setSeatHeight('chair');
    } else if (!isSitAnim && seatHeight !== 'none') {
      setSeatHeight('none');
    }
  };

  const handleUploadFbx = (url: string, _name: string) => {
    // Revoke previous blob URL to prevent memory leaks. Only revoke blobs, not manifest URLs.
    if (activeFbxUrl?.startsWith('blob:')) {
      URL.revokeObjectURL(activeFbxUrl);
    }
    setSelectedAnimId(null);
    setActiveUalClip(null);
    setActiveFbxUrl(url);
  };

  // Revoke any outstanding blob URLs on page unmount
  useEffect(() => {
    return () => {
      if (activeFbxUrl?.startsWith('blob:')) URL.revokeObjectURL(activeFbxUrl);
      if (activeVrmUrl?.startsWith('blob:')) URL.revokeObjectURL(activeVrmUrl);
    };
  }, [activeFbxUrl, activeVrmUrl]);

  const handleResetCamera = () => {
    canvasRef.current?.resetCamera();
  };

  const handleResetDragOffset = () => {
    setDragOffset({ x: 0, y: 0, z: 0 });
    setDragClamped(false);
    // Re-run snap by bouncing the anim id through handleSelectAnim if one is selected
    if (selectedAnimId) handleSelectAnim(selectedAnimId);
  };

  // Build avatar ID for session entries (decision #1 schema)
  const getAvatarId = (): string => {
    if (!selectedAvatar) return activeVrmUrl ?? 'unknown';
    return `${selectedAvatar.collection_slug ?? selectedCollectionSlug ?? 'unknown'}:${selectedAvatar.id}`;
  };

  // Session notice — shown inline near the Save / Export manifest buttons.
  // Replaces silent no-ops and bare alert() calls.
  const [sessionNotice, setSessionNotice] = useState<{ tone: 'error' | 'info'; msg: string } | null>(null);
  useEffect(() => {
    if (!sessionNotice) return;
    const t = setTimeout(() => setSessionNotice(null), 5000);
    return () => clearTimeout(t);
  }, [sessionNotice]);

  const handleSaveToSession = () => {
    if (!activeVrmUrl) {
      setSessionNotice({ tone: 'error', msg: 'Load an avatar first.' });
      return;
    }
    const collectionSlug = selectedAvatar?.collection_slug ?? selectedCollectionSlug ?? '';
    if (!collectionSlug) {
      setSessionNotice({
        tone: 'error',
        msg: "Pick a collection before saving. Local VRM uploads can't save to session without collection context.",
      });
      return;
    }

    const currentCollection = collections.find((c) => c.slug === collectionSlug);

    const entry = makeEntry({
      scope: rigScope,
      collectionSlug,
      avatarId: rigScope === 'avatar' ? getAvatarId() : undefined,
      displayName:
        rigScope === 'avatar'
          ? (selectedAvatar?.name ?? 'local-upload')
          : (currentCollection?.name ?? collectionSlug),
      animationId: selectedAnimId,
      seatHeight,
      facingDeg: avatarFacingDeg,
      offset: { ...dragOffset },
    });
    setSessionEntries((prev) => [...prev, entry]);
  };

  // Scope switch handler — prompts only when there's an unsaved offset (decision C)
  const hasUnsavedOffset = dragOffset.x !== 0 || dragOffset.y !== 0 || dragOffset.z !== 0;

  const handleScopeSwitch = (newScope: RigCorrectionScope) => {
    if (newScope === rigScope) return;
    if (hasUnsavedOffset) {
      setScopeSwitchPrompt(newScope);
    } else {
      setRigScope(newScope);
    }
  };

  const handleScopeSwitchTransfer = () => {
    if (scopeSwitchPrompt) setRigScope(scopeSwitchPrompt);
    setScopeSwitchPrompt(null);
  };

  const handleScopeSwitchDiscard = () => {
    if (scopeSwitchPrompt) setRigScope(scopeSwitchPrompt);
    setDragOffset({ x: 0, y: 0, z: 0 });
    setDragClamped(false);
    if (selectedAnimId) handleSelectAnim(selectedAnimId); // re-snap
    setScopeSwitchPrompt(null);
  };

  const handleScopeSwitchCancel = () => {
    setScopeSwitchPrompt(null);
  };

  // Resolve current avatar's effective offset from session entries (for display)
  const currentCollectionSlug = selectedAvatar?.collection_slug ?? selectedCollectionSlug ?? '';
  const resolvedCorrection = selectedAvatar
    ? resolveEffectiveOffset(sessionEntries, getAvatarId(), currentCollectionSlug)
    : null;

  const handleExportSession = () => {
    if (sessionEntries.length === 0) return;
    exportSession(sessionEntries);
  };

  // ── Batch pfp render + upload ───────────────────────────────────────────
  // Iterates every avatar in the currently selected collection, renders each
  // via the same framing/pose/animation knobs the user tuned live, POSTs each
  // PNG to avatar-api which writes it to R2 at thumbs/<slug>/<id>-pfp.png.
  // Rendered URLs are written into pfpUrlOverrides so the next manifest export
  // reflects the freshly-generated altii.co URLs instead of whatever avatar-api
  // originally returned as thumbnail_url.
  const { authenticated, login, getAccessToken } = usePrivy();
  const [pfpUrlOverrides, setPfpUrlOverrides] = useState<Record<string, string>>({});
  const [batchStatus, setBatchStatus] = useState<{
    running: boolean;
    done: number;
    total: number;
    failed: number;
    stop: boolean;
    lastError: string | null;
  }>({ running: false, done: 0, total: 0, failed: 0, stop: false, lastError: null });
  const batchStopRef = useRef(false);

  const handleBatchStop = () => {
    batchStopRef.current = true;
    setBatchStatus((s) => ({ ...s, stop: true }));
  };

  const handleBatchRenderPfp = async () => {
    if (!selectedCollectionSlug) {
      setSessionNotice({ tone: 'error', msg: 'Select a collection first' });
      return;
    }
    if (!authenticated) {
      setSessionNotice({ tone: 'error', msg: 'Sign in required for batch upload' });
      login();
      return;
    }
    const collectionAvatars = collectionAvatarsCache[selectedCollectionSlug] ?? avatars;
    if (!collectionAvatars || collectionAvatars.length === 0) {
      setSessionNotice({ tone: 'error', msg: 'No avatars to render in this collection' });
      return;
    }

    const token = await getAccessToken();
    if (!token) {
      setSessionNotice({ tone: 'error', msg: 'Sign-in token unavailable; please sign in again' });
      return;
    }

    batchStopRef.current = false;
    const slug = selectedCollectionSlug;
    setBatchStatus({ running: true, done: 0, total: collectionAvatars.length, failed: 0, stop: false, lastError: null });

    for (let i = 0; i < collectionAvatars.length; i++) {
      if (batchStopRef.current) break;
      const avatar = collectionAvatars[i];
      const vrmUrl = getVrmUrl(avatar);
      if (!vrmUrl) {
        setBatchStatus((s) => ({ ...s, failed: s.failed + 1, done: s.done + 1 }));
        continue;
      }
      try {
        const dataUrl = await renderPfpThumbnail({
          vrmUrl,
          // Framing defaults match what AvatarThumbnailsPage ships today.
          // A later pass can thread the live framing knobs in — for now use
          // the same defaults the admin dashboard uses so output is parity.
          outputSize: 256,
          animation: 'anim_idle',
        });
        const result = await uploadPfpThumbnail(slug, avatar.id, dataUrl, token);
        if (result.ok === true) {
          const ok = result;
          setPfpUrlOverrides((prev) => ({ ...prev, [`${slug}:${avatar.id}`]: ok.url }));
          setBatchStatus((s) => ({ ...s, done: s.done + 1 }));
        } else {
          const fail = result;
          setBatchStatus((s) => ({
            ...s,
            done: s.done + 1,
            failed: s.failed + 1,
            lastError: `${avatar.id}: ${fail.error}${fail.message ? ` — ${fail.message}` : ''}`,
          }));
        }
      } catch (err: any) {
        setBatchStatus((s) => ({
          ...s,
          done: s.done + 1,
          failed: s.failed + 1,
          lastError: `${avatar.id}: ${err?.message ?? String(err)}`,
        }));
      }
    }

    setBatchStatus((s) => ({ ...s, running: false }));
    setSessionNotice({
      tone: 'info',
      msg: `Batch pfp render done. ${collectionAvatars.length - (batchStopRef.current ? collectionAvatars.length - (batchStatus.done + 1) : 0)} avatars processed.`,
    });
  };

  // Manifest export — one JSON file per collection touched this session OR
  // for the current collection if pfp batch-render produced fresh URLs.
  // Cascade is pre-resolved here; consumer doesn't need to understand scope.
  const handleExportManifest = () => {
    // Slugs worth emitting: those with rig-correction entries, PLUS the
    // currently selected collection if any batch-rendered pfp URLs exist.
    const touchedSlugs = new Set(collectionsTouchedBySession(sessionEntries));
    if (selectedCollectionSlug) {
      const hasOverrides = Object.keys(pfpUrlOverrides).some((k) => k.startsWith(`${selectedCollectionSlug}:`));
      if (hasOverrides) touchedSlugs.add(selectedCollectionSlug);
    }

    if (touchedSlugs.size === 0) {
      setSessionNotice({
        tone: 'error',
        msg: 'Nothing to export. Save a rig correction or run a pfp batch render first.',
      });
      return;
    }

    let emitted = 0;
    for (const slug of touchedSlugs) {
      const collection = collections.find((c) => c.slug === slug);
      const collectionAvatars = collectionAvatarsCache[slug];
      if (!collection || !collectionAvatars) {
        console.warn(`[manifest] skipping ${slug} — collection metadata not cached. Visit the collection first.`);
        continue;
      }

      // Splice any batch-rendered pfp URLs onto the avatars for THIS slug so
      // buildCollectionManifest sees the fresh altii.co R2 URLs via
      // avatar.thumbnail_url. Keeps the manifest.ts signature unchanged.
      const withOverrides = collectionAvatars.map((a) => {
        const override = pfpUrlOverrides[`${slug}:${a.id}`];
        return override ? { ...a, thumbnail_url: override } : a;
      });

      const manifest = buildCollectionManifest(collection, withOverrides, sessionEntries);
      downloadManifest(manifest);
      emitted++;
    }
    if (emitted === 0) {
      setSessionNotice({
        tone: 'error',
        msg: 'No manifests emitted. Visit each touched collection at least once so its metadata is cached, then try again.',
      });
    } else {
      setSessionNotice({ tone: 'info', msg: `Exported ${emitted} manifest${emitted === 1 ? '' : 's'}.` });
    }
  };

  // FB thumbnail capture — renders the current canvas to a 512×512 PNG download.
  // Uses the current playing animation. For canonical fb-thumbnails across a
  // collection, pick anim_idle first for consistency.
  const handleCaptureFbThumbnail = () => {
    if (!activeVrmUrl) return;
    const canvas = document.querySelector<HTMLCanvasElement>('canvas');
    if (!canvas) return;
    // Export at native canvas resolution; downstream resizing happens upstream
    const dataUrl = canvas.toDataURL('image/png');
    const idStr = selectedAvatar
      ? `${selectedAvatar.collection_slug ?? 'local'}-${selectedAvatar.id}`
      : 'local-upload';
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `${idStr}-fb.png`;
    a.click();
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Page header */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border shrink-0">
        <span className="text-xs text-muted-foreground">altiico</span>
        <span className="text-xs text-muted-foreground">/</span>
        <span className="text-xs font-medium">Preview</span>
        {activeVrmUrl && (
          <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-primary/20 text-primary">
            VRM
          </span>
        )}
        {activeFbxUrl && (
          <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">
            FBX
          </span>
        )}
        {measuredHeight !== null && (() => {
          const inBand = measuredHeight >= AVATAR_TARGET_HEIGHT_MIN && measuredHeight <= AVATAR_TARGET_HEIGHT_MAX;
          const tone = inBand
            ? 'bg-emerald-500/20 text-emerald-400'
            : 'bg-yellow-500/20 text-yellow-400';
          const note = inBand ? '' : (measuredHeight > AVATAR_TARGET_HEIGHT_MAX ? ' over' : ' under');
          return (
            <span className={`ml-1 text-[10px] px-1.5 py-0.5 rounded ${tone}`} title={`Target: ${AVATAR_TARGET_HEIGHT_MIN}m–${AVATAR_TARGET_HEIGHT_MAX}m`}>
              H: {measuredHeight.toFixed(2)}m{note}
            </span>
          );
        })()}
        {/* Session entry count chip — breakdown by scope */}
        {sessionEntries.length > 0 && (() => {
          const collectionCount = sessionEntries.filter((e) => e.scope === 'collection').length;
          const avatarCount = sessionEntries.filter((e) => e.scope === 'avatar').length;
          return (
            <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300"
                  title={`${collectionCount} set-scoped + ${avatarCount} avatar-scoped`}>
              Session: {collectionCount}c + {avatarCount}a
            </span>
          );
        })()}
      </div>

      {/* Three-column layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Collections + Avatar grid */}
        <div className="w-[260px] shrink-0 border-r border-border p-3 overflow-hidden flex flex-col">
          <LeftColumn
            collections={collections}
            collectionsLoading={collectionsLoading}
            selectedCollectionSlug={selectedCollectionSlug}
            onSelectCollection={setSelectedCollectionSlug}
            avatars={avatars}
            avatarsLoading={avatarsLoading}
            selectedAvatar={selectedAvatar}
            onSelectAvatar={handleSelectAvatar}
            onUploadVrm={handleUploadVrm}
          />
        </div>

        {/* Center: IsometricCanvas */}
        <div className="flex-1 flex items-center justify-center bg-muted/20 min-w-0">
          {activeVrmUrl ? (
            <Suspense
              fallback={
                <div className="flex items-center justify-center w-full h-full text-xs text-muted-foreground">
                  Canvas loading...
                </div>
              }
            >
              <IsometricCanvas
                ref={canvasRef}
                vrmUrl={activeVrmUrl}
                fbxUrl={activeFbxUrl ?? undefined}
                ualClip={activeUalClip ?? undefined}
                playing={isPlaying}
                loop={loop}
                speed={speed}
                showBones={showBones}
                showBounds={showBounds}
                seatHeight={seatHeight}
                avatarFacingDeg={avatarFacingDeg}
                dragEnabled={dragEnabled}
                onDragOffsetChange={(v) => setDragOffset({ x: v.x, y: v.y, z: v.z })}
                onDragClampedChange={setDragClamped}
                props={SHOW_PROPS ? propInstancesList : []}
                onLoad={handleVrmLoaded}
              />
            </Suspense>
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 text-center p-8">
              <div className="text-muted-foreground text-sm">No avatar selected</div>
              <div className="text-xs text-muted-foreground/60 max-w-xs">
                Pick a collection and avatar from the left panel, or drag a VRM file onto the left column.
              </div>
            </div>
          )}
        </div>

        {/* Right: Animation controls */}
        <div className="w-[280px] shrink-0 border-l border-border p-3 overflow-hidden">
          <RightColumn
            animations={animations}
            selectedAnimId={selectedAnimId}
            onSelectAnim={handleSelectAnim}
            isPlaying={isPlaying}
            onTogglePlay={() => setIsPlaying((p) => !p)}
            loop={loop}
            onToggleLoop={setLoop}
            speed={speed}
            onSpeedChange={setSpeed}
            onResetCamera={handleResetCamera}
            showBones={showBones}
            onToggleBones={setShowBones}
            showBounds={showBounds}
            onToggleBounds={setShowBounds}
            onUploadFbx={handleUploadFbx}
            propDefinitions={propDefinitions}
            activeProps={activeProps}
            onToggleProp={togglePropActive}
            onUpdateProp={updatePropInstance}
            dragEnabled={dragEnabled}
            onToggleDrag={setDragEnabled}
            dragOffset={dragOffset}
            dragClamped={dragClamped}
            onResetDragOffset={handleResetDragOffset}
            onSaveToSession={handleSaveToSession}
            onExportSession={handleExportSession}
            onExportManifest={handleExportManifest}
            onCaptureFbThumbnail={handleCaptureFbThumbnail}
            onBatchRenderPfp={handleBatchRenderPfp}
            onBatchStop={handleBatchStop}
            batchStatus={batchStatus}
            sessionCount={sessionEntries.length}
            rigScope={rigScope}
            onScopeSwitch={handleScopeSwitch}
            scopeSwitchPrompt={scopeSwitchPrompt}
            onScopeSwitchTransfer={handleScopeSwitchTransfer}
            onScopeSwitchDiscard={handleScopeSwitchDiscard}
            onScopeSwitchCancel={handleScopeSwitchCancel}
            resolvedCorrection={resolvedCorrection}
            avatarSessionCount={sessionEntries.filter((e) => e.scope === 'avatar').length}
            collectionSessionCount={sessionEntries.filter((e) => e.scope === 'collection').length}
            selectedCollectionName={
              collections.find((c) => c.slug === (selectedAvatar?.collection_slug ?? selectedCollectionSlug))?.name ?? null
            }
            seatHeight={seatHeight}
            onSeatHeightChange={(v) => {
              setSeatHeight(v);
              // Mirror hubzz editor: when seat height changes, active sittable
              // props raise to that height so the prop's seat surface lines up
              // with where the avatar's pelvis will land (0.3 above its
              // animation-baked position).
              const newY = v === 'none' ? 0 : HUBZZ_SEAT_HEIGHTS[v];
              setActiveProps((prev) => {
                const next: Record<string, PropInstance> = {};
                for (const [id, inst] of Object.entries(prev)) {
                  next[id] = {
                    ...inst,
                    offset: { ...inst.offset, y: newY },
                  };
                }
                return next;
              });
            }}
            avatarFacingDeg={avatarFacingDeg}
            onAvatarFacingDegChange={setAvatarFacingDeg}
            offsetClearedNotice={offsetClearedNotice}
            sessionNotice={sessionNotice}
          />
        </div>
      </div>
    </div>
  );
}
