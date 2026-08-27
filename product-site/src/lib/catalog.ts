export type EvidenceState = 'verified' | 'partial' | 'review';
export type ReadinessState = 'ready' | 'staged' | 'preview';

export type Evidence = {
  source: 'fixture' | 'legacy-catalog';
  snapshotId?: string;
  state: EvidenceState;
  checkedAt?: string;
  notes: string[];
};

export type Avatar = {
  id: string;
  slug: string;
  name: string;
  setSlug: string;
  role: 'primary' | 'supporting';
  sourceAssetId?: string;
  apiAvatarId?: string;
  tokenId?: string;
  thumbnailUrl?: string;
  originalAssetUrl?: string;
  vrmSpec?: string;
  fileSize?: number;
  traits: { label: string; value: string; source: 'product' | 'evidence' }[];
  evidence: Evidence;
};

export type AvatarSet = {
  id: string;
  slug: string;
  name: string;
  description: string;
  readiness: ReadinessState;
  chain?: string;
  contract?: string;
  license?: string;
  sourceSetId?: string;
  evidence: Evidence;
  avatars: Avatar[];
};

const fixtures: AvatarSet[] = [
  {
    id: 'set-core-entity-lab',
    slug: 'core-entity-lab',
    name: 'Core Entity Lab',
    description: 'A local product fixture used to establish Altiico discovery and identity presentation before live catalog integration.',
    readiness: 'ready',
    chain: 'fixture',
    license: 'Internal fixture',
    evidence: { source: 'fixture', state: 'verified', notes: ['Local UI fixture. Not production catalog data.'] },
    avatars: [
      {
        id: 'avatar-robot-anchor',
        slug: 'robot-anchor',
        name: 'Robot Anchor',
        setSlug: 'core-entity-lab',
        role: 'primary',
        vrmSpec: 'pending source import',
        traits: [
          { label: 'ROLE', value: 'PRIMARY ENTITY', source: 'product' },
          { label: 'VISUAL', value: 'ROBOT ANCHOR', source: 'product' }
        ],
        evidence: { source: 'fixture', state: 'review', notes: ['Canonical 100Avatars robot asset will replace this illustration slot after provenance import.'] }
      },
      {
        id: 'avatar-scout-01',
        slug: 'scout-01',
        name: 'Scout 01',
        setSlug: 'core-entity-lab',
        role: 'supporting',
        traits: [{ label: 'ROLE', value: 'SUPPORTING', source: 'product' }],
        evidence: { source: 'fixture', state: 'partial', notes: ['Supporting fixture.'] }
      }
    ]
  },
  {
    id: 'set-evidence-preview',
    slug: 'evidence-preview',
    name: 'Evidence Preview',
    description: 'A second local fixture that tests review and evidence states without claiming live catalog status.',
    readiness: 'preview',
    chain: 'fixture',
    license: 'Review required',
    evidence: { source: 'fixture', state: 'partial', notes: ['Local evidence-state fixture.'] },
    avatars: []
  }
];

export interface AvatarCatalogAdapter {
  listSets(): Promise<AvatarSet[]>;
  getSetBySlug(slug: string): Promise<AvatarSet | null>;
  getAvatarBySlug(setSlug: string, avatarSlug: string): Promise<Avatar | null>;
}

export const localCatalogAdapter: AvatarCatalogAdapter = {
  async listSets() { return fixtures; },
  async getSetBySlug(slug) { return fixtures.find((set) => set.slug === slug) ?? null; },
  async getAvatarBySlug(setSlug, avatarSlug) {
    return fixtures.find((set) => set.slug === setSlug)?.avatars.find((avatar) => avatar.slug === avatarSlug) ?? null;
  }
};
