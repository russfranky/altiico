/**
 * Pipeline — visual reference of the Hubzz avatar lifecycle.
 *
 * End-to-end flow: NFT contract → avatar-api → optimizer → R2 → admin lifecycle
 * → altiico QA → hubzz engine → in-world. Each stage is a clickable node with
 * detail about endpoints, code paths, and credentials. Counters on live stages
 * pull from the avatar-api /health + /collections endpoints.
 *
 * Source of truth: NORTH_STAR.md pipeline diagram + hubzz-alpha CLAUDE.md.
 * When the pipeline changes, update the NODES array below and the north star.
 */
import { useEffect, useState } from 'react';
import { API_BASE_URL } from '@/config/api';
import { obs } from '@/lib/obs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Package,
  Server,
  Zap,
  Cloud,
  LayoutDashboard,
  Microscope,
  Gamepad2,
  User,
} from 'lucide-react';

interface PipelineNodeSpec {
  id: string;
  title: string;
  icon: typeof Package;
  summary: string;
  detail: {
    purpose: string;
    endpoints?: string[];
    filePaths?: string[];
    credentials?: string;
  };
  /** If true, fetches live counts from avatar-api and displays on the node. */
  liveStatus?: 'ingest' | 'r2' | 'admin' | 'altiico-session';
  /** One of altiico / hubzz-alpha / avatar-api / r2 — for left-side ownership color strip. */
  owner: 'external' | 'avatar-api' | 'optimizer' | 'r2' | 'hubzz-admin' | 'altiico' | 'hubzz-engine';
  /** Which section of the pipeline this stage belongs to. */
  band: 'acquisition' | 'processing' | 'consumption';
}

const BAND_META: Record<PipelineNodeSpec['band'], { label: string; hint: string }> = {
  acquisition: { label: 'Acquisition', hint: 'Fetch + record' },
  processing:  { label: 'Processing',  hint: 'Normalize + store' },
  consumption: { label: 'Consumption', hint: 'Serve + render' },
};

const NODES: PipelineNodeSpec[] = [
  {
    id: 'source',
    title: 'Source',
    icon: Package,
    summary: 'NFT contract or open-source creator drop',
    owner: 'external',
    band: 'acquisition',
    detail: {
      purpose:
        'Origin of all avatar assets. Either an on-chain NFT collection (Ethereum, Somnia) or a static drop (Arweave, IPFS, direct VRM URL).',
      endpoints: ['External — OpenSea collection pages, Arweave gateways, IPFS pinning services'],
      credentials: 'None at source; Moralis API key needed for on-chain reads (hubzz server-side).',
    },
  },
  {
    id: 'ingest',
    title: 'Ingest',
    icon: Server,
    summary: 'Fetch VRM URLs + NFT metadata by token id',
    owner: 'avatar-api',
    band: 'acquisition',
    liveStatus: 'ingest',
    detail: {
      purpose:
        'Scrapes NFT metadata across a tokenId range using a source pattern with {id} placeholder. Writes pending records to avatars.db (sql.js in-memory + persisted).',
      endpoints: [
        'POST /api/collections/:slug/ingest',
        'GET /avatars?collection=:slug — progress read',
      ],
      filePaths: [
        'packages/avatar-api/src/routes/ingest.ts',
        'packages/avatar-api/src/ingest/ethereum.ts',
        'packages/avatar-api/src/ingest/run.ts',
      ],
      credentials: 'Moralis API key (for Ethereum NFT metadata); none for URL-pattern ingest.',
    },
  },
  {
    id: 'normalize',
    title: 'Normalize',
    icon: Zap,
    summary: 'Bake size + scale spring params (object-model §7)',
    owner: 'optimizer',
    band: 'processing',
    detail: {
      purpose:
        'Measures bbox, bakes the scale factor into the root transform so every avatar ships at root scale 1.0 inside the target height band. Patches VRM spring-bone params (hitRadius × s, stiffness / s, gravityPower × s) so hair physics feel right post-scale. Stores the original scale factor in avatars.normalized_scale for audit/reversibility.',
      endpoints: [
        'Internal — runs before compress in the batch pipeline',
      ],
      filePaths: [
        'packages/avatar-api/src/optimize/batch.ts',
        'docs/object-model.md §7',
      ],
    },
  },
  {
    id: 'compress',
    title: 'Compress',
    icon: Zap,
    summary: 'Meshopt + Draco + texture resize (preset=aggressive)',
    owner: 'optimizer',
    band: 'processing',
    detail: {
      purpose:
        'VRM is run through vrm-optimizer on port 3333 after normalization. Aggressive preset typically achieves 60–80% file size reduction. Produces optimized_vrm_url.',
      endpoints: [
        'POST http://155.138.214.59:3333/optimize?preset=aggressive',
        'POST http://155.138.214.59:3333/optimize?preset=balanced',
      ],
      filePaths: ['packages/avatar-api/src/optimize/batch.ts'],
    },
  },
  {
    id: 'r2',
    title: 'Storage',
    icon: Cloud,
    summary: 'Cloudflare R2 — canonical asset store',
    owner: 'r2',
    band: 'processing',
    liveStatus: 'r2',
    detail: {
      purpose:
        'All published avatar assets live here. URLs constructed as /files/avatars/<slug>/<tokenId>.vrm. Served via the hubzz-assets-worker Cloudflare Worker.',
      endpoints: [
        'https://hubzz-assets-worker.hubzzhq.workers.dev/files/avatars/<slug>/',
        'https://hubzz-assets-worker.hubzzhq.workers.dev/files/thumbs/<slug>/',
        'https://hubzz-assets-worker.hubzzhq.workers.dev/files/collections/<slug>/manifest.json',
      ],
      filePaths: [
        'packages/avatar-api/src/optimize/batch.ts (uploads after optimize)',
      ],
      credentials: 'R2 API token stored in hubzz server env, never exposed to altiico.',
    },
  },
  {
    id: 'admin',
    title: 'Admin',
    icon: LayoutDashboard,
    summary: 'Lifecycle: draft → ingesting → staged → published',
    owner: 'hubzz-admin',
    band: 'processing',
    liveStatus: 'admin',
    detail: {
      purpose:
        'Collection status machine gates in-world visibility. Only published collections appear in avatar selection; staged are visible to admins/QA; draft is invisible.',
      endpoints: [
        'GET /api/admin/collections',
        'PATCH /api/admin/collections/:slug/status',
      ],
      filePaths: [
        'packages/server/src/Routes/AdminCollectionsRoutes.ts',
        'packages/admin/src/components/admin/assets/CollectionsTab.tsx',
      ],
      credentials: 'hbz_ access token + api.admin permission.',
    },
  },
  {
    id: 'altiico',
    title: 'QA',
    icon: Microscope,
    summary: 'Rig inspection, corrections, manifest export',
    owner: 'altiico',
    band: 'processing',
    liveStatus: 'altiico-session',
    detail: {
      purpose:
        'Human-in-the-loop evaluation of each avatar. Drag-to-correct rig offsets, per-avatar and per-collection. Manifest export produces the JSON hubzz engine consumes.',
      endpoints: [
        '/preview — rig correction surface',
        'GET http://avatar-api:1233/collections — data source',
      ],
      filePaths: [
        'src/pages/AnimationPreviewPage.tsx',
        'src/lib/manifest.ts',
        'src/lib/rigCorrection.ts',
      ],
    },
  },
  {
    id: 'engine',
    title: 'Engine',
    icon: Gamepad2,
    summary: 'NFTManager + SetAvatar — wallet or published-R2 path',
    owner: 'hubzz-engine',
    band: 'consumption',
    detail: {
      purpose:
        'Two paths: (1) Wallet path — NFTManager.updateWalletCache calls Moralis, filters NFTs with vrm_url metadata, constructs R2 URLs for published collections. (2) Default path — SetAvatar.getPublishedR2Avatars fetches from avatar-api for the avatar picker.',
      endpoints: [
        'NFTManager.ts — wallet NFT fetching',
        'SetAvatar.ts — in-game avatar selection',
      ],
      filePaths: [
        'packages/server/src/Blockchain/NFTManager.ts',
        'packages/server/src/Messages/SetAvatar.ts',
      ],
      credentials: 'Moralis JWT (server config.json).',
    },
  },
  {
    id: 'world',
    title: 'In-world',
    icon: User,
    summary: 'EntityAvatar applies VRM + rig correction + animation',
    owner: 'hubzz-engine',
    band: 'consumption',
    detail: {
      purpose:
        'Avatar loads in the Three.js engine at root scale 1.0 (post-ingest normalization). Pelvis-driven sit placement, outline shader, toon material. Rig corrections (from altiico manifests) apply on top of snapToTilePosition.',
      filePaths: [
        'packages/client/src/engine/entities/avatar/EntityAvatar.ts',
        'packages/client/src/engine/entities/avatar/AvatarVRMManager.ts',
        'packages/client/src/engine/misc/MixamoLoader.ts',
      ],
    },
  },
];

// Tinted backgrounds for the icon tile — same hue, lighter weight.
// Gives each stage a distinct color identity without looking like a dashboard.
const OWNER_TINTS: Record<PipelineNodeSpec['owner'], string> = {
  external:      'bg-slate-500/10   text-slate-400   ring-slate-500/20',
  'avatar-api':  'bg-cyan-500/10    text-cyan-400    ring-cyan-500/20',
  optimizer:     'bg-yellow-500/10  text-yellow-400  ring-yellow-500/20',
  r2:            'bg-orange-500/10  text-orange-400  ring-orange-500/20',
  'hubzz-admin': 'bg-purple-500/10  text-purple-400  ring-purple-500/20',
  altiico:       'bg-primary/10     text-primary     ring-primary/20',
  'hubzz-engine':'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
};

interface LiveCounts {
  avatarApiOk: boolean | null;
  totalAvatars: number | null;
  totalCollections: number | null;
  statusBreakdown: Record<string, number> | null;
}

function useLiveCounts(): LiveCounts {
  const [state, setState] = useState<LiveCounts>({
    avatarApiOk: null,
    totalAvatars: null,
    totalCollections: null,
    statusBreakdown: null,
  });

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [, collectionsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/health`),
          fetch(`${API_BASE_URL}/collections`),
        ]);
        const { collections } = await collectionsRes.json() as { collections: Array<{ status: string; avatar_count: number }> };

        const statusBreakdown: Record<string, number> = {};
        let totalAvatars = 0;
        for (const c of collections) {
          statusBreakdown[c.status] = (statusBreakdown[c.status] ?? 0) + 1;
          totalAvatars += c.avatar_count ?? 0;
        }
        if (!cancelled) {
          setState({
            avatarApiOk: true,
            totalAvatars,
            totalCollections: collections.length,
            statusBreakdown,
          });
        }
      } catch (err) {
        // obs-only — this polls every 30s, so Sentry would alert-flood on a
        // sustained avatar-api outage. Local signal is enough; the Sentry
        // signal for the underlying fetch failure comes from avatarService.
        obs.warn('pipeline.health', 'avatar-api health check failed', { avatarApiOk: false }, {
          err: err instanceof Error ? err.message : String(err),
        });
        if (!cancelled) {
          setState((s) => ({ ...s, avatarApiOk: false }));
        }
      }
    };
    load();
    const interval = setInterval(load, 30000); // refresh every 30s
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return state;
}

function renderLiveStatus(node: PipelineNodeSpec, counts: LiveCounts): string | null {
  if (!node.liveStatus) return null;
  if (counts.avatarApiOk === null) return 'Loading...';
  if (counts.avatarApiOk === false) return 'avatar-api offline';

  switch (node.liveStatus) {
    case 'ingest':
      return `${counts.totalCollections ?? 0} collections / ${counts.totalAvatars ?? 0} avatars`;
    case 'r2':
      return `${counts.totalAvatars ?? 0} files hosted`;
    case 'admin':
      if (!counts.statusBreakdown) return null;
      return Object.entries(counts.statusBreakdown)
        .map(([k, v]) => `${v} ${k}`)
        .join(' · ');
    case 'altiico-session':
      return 'Session-scoped — see Preview';
    default:
      return null;
  }
}

/**
 * Single node — one per row. Reads like a list item, not a card.
 * Left column: big step number + icon tile. Right column: title + full
 * description. Live count (if any) is an inline chip next to the title.
 * Click opens the detail modal for endpoints / file paths / credentials.
 */
function PipelineStep({
  node,
  counts,
  stepNumber,
  onClick,
}: {
  node: PipelineNodeSpec;
  counts: LiveCounts;
  stepNumber: number;
  onClick: () => void;
}) {
  const Icon = node.icon;
  const liveText = renderLiveStatus(node, counts);

  return (
    <button
      onClick={onClick}
      className="w-full text-left group flex gap-5 py-5 px-2 border-t border-border/40 hover:bg-muted/20 transition-colors"
    >
      {/* Left rail — step number above icon */}
      <div className="flex flex-col items-center gap-2 shrink-0 w-14 pt-1">
        <span className="text-xs font-mono text-muted-foreground/60">
          {stepNumber.toString().padStart(2, '0')}
        </span>
        <div className={`flex items-center justify-center size-11 rounded-lg ring-1 ${OWNER_TINTS[node.owner]}`}>
          <Icon className="size-5" />
        </div>
      </div>

      {/* Content — full explanation */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-3 flex-wrap">
          <h3 className="text-base font-semibold tracking-tight">{node.title}</h3>
          {liveText && (
            <span className="text-[11px] px-2 py-0.5 rounded bg-primary/10 text-primary font-mono">
              {liveText}
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
          {node.detail.purpose}
        </p>
        <div className="mt-2 text-xs text-muted-foreground/70 opacity-0 group-hover:opacity-100 transition-opacity">
          Click for endpoints, file paths{node.detail.credentials ? ', credentials' : ''} →
        </div>
      </div>
    </button>
  );
}

/**
 * Banded list — Acquisition / Processing / Consumption dividers with the
 * steps underneath. Plain-text band headers, no boxes. Every step shows
 * its full purpose inline; no truncation, no click-required reading.
 */
function StepList({
  counts,
  onNodeClick,
}: {
  counts: LiveCounts;
  onNodeClick: (id: string) => void;
}) {
  const bands: PipelineNodeSpec['band'][] = ['acquisition', 'processing', 'consumption'];

  return (
    <div className="flex flex-col">
      {bands.map((band) => {
        const nodes = NODES.filter((n) => n.band === band);
        if (nodes.length === 0) return null;
        const meta = BAND_META[band];
        return (
          <section key={band} className="mt-8 first:mt-0">
            <header className="flex items-baseline gap-3 mb-1 px-2">
              <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-foreground">
                {meta.label}
              </h2>
              <span className="text-xs text-muted-foreground">{meta.hint}</span>
            </header>
            <div className="flex flex-col">
              {nodes.map((node) => {
                const stepNumber = NODES.findIndex((n) => n.id === node.id) + 1;
                return (
                  <PipelineStep
                    key={node.id}
                    node={node}
                    counts={counts}
                    stepNumber={stepNumber}
                    onClick={() => onNodeClick(node.id)}
                  />
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}

export function PipelineFlow() {
  const counts = useLiveCounts();
  const [openNodeId, setOpenNodeId] = useState<string | null>(null);

  const openNode = NODES.find((n) => n.id === openNodeId) ?? null;

  return (
    <>
      {counts.avatarApiOk === false && (
        <div className="flex justify-center">
          <div className="inline-block px-3 py-1 rounded bg-red-500/10 text-red-400 text-xs">
            avatar-api unreachable — live counts disabled
          </div>
        </div>
      )}

      <StepList counts={counts} onNodeClick={setOpenNodeId} />

      {/* Detail modal */}
      <Dialog open={openNode !== null} onOpenChange={(open) => !open && setOpenNodeId(null)}>
        <DialogContent className="sm:max-w-xl">
          {openNode && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-3">
                  <div className={`flex items-center justify-center size-10 rounded-lg ring-1 ${OWNER_TINTS[openNode.owner]}`}>
                    <openNode.icon className="size-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground/80">
                      {BAND_META[openNode.band].label}
                    </div>
                    <DialogTitle>{openNode.title}</DialogTitle>
                  </div>
                </div>
                <DialogDescription className="pt-2 text-left">
                  {openNode.detail.purpose}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3 text-sm">
                {openNode.detail.endpoints && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                      Endpoints
                    </div>
                    <ul className="space-y-1">
                      {openNode.detail.endpoints.map((e) => (
                        <li key={e} className="font-mono text-xs bg-muted rounded px-2 py-1">
                          {e}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {openNode.detail.filePaths && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                      Code paths
                    </div>
                    <ul className="space-y-1">
                      {openNode.detail.filePaths.map((p) => (
                        <li key={p} className="font-mono text-xs bg-muted rounded px-2 py-1">
                          {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {openNode.detail.credentials && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                      Credentials
                    </div>
                    <p className="text-xs text-muted-foreground">{openNode.detail.credentials}</p>
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

    </>
  );
}

export default function PipelinePage() {
  return (
    <div className="flex flex-col gap-10 p-6 md:p-10 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex flex-col gap-3 mt-2">
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
          Avatar pipeline
        </h1>
        <p className="text-base text-muted-foreground leading-relaxed max-w-2xl">
          How an avatar gets from source (an NFT contract or a creator drop)
          into the hubzz world. Nine stages across three phases: acquiring,
          processing, and serving. Click any stage for endpoints, file paths,
          and credentials.
        </p>
      </div>

      <PipelineFlow />
    </div>
  );
}
