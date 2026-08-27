export type LegacyAltiicoStageClass = 'bulk_ready' | 'partial_ready' | 'preview_ready' | 'deferred';

export type LegacyAltiicoStagingSet = {
  set: {
    schemaVersion: number;
    slug: string;
    name: string;
    description: string | null;
    chain: string | null;
    contract: string | null;
    storageProvider: string | null;
    ingestSource: string | null;
    license: string | null;
    author: string | null;
    bannerUrl: string | null;
    pfpUrl: string | null;
    purchaseGated: boolean | null;
    listed: boolean;
    status: string;
    avatarCount: number;
  };
  stageClass: LegacyAltiicoStageClass;
  sourceAssets: {
    path: string;
    count: number;
    mode: string;
    reachableCount: number;
    binaryValidatedCount: number;
    validationScope: string;
  };
  coverage: {
    knownAvatars: number;
    reachableSourceAvatars: number;
    binaryValidatedSourceAvatars: number;
    catalogSupply: number;
    coverageRatio: number;
  };
  sampleEvidence: {
    canonicalUrl: string | null;
    transportUrl: string | null;
    vrmSpec: string | null;
    fileSizeOriginal: number | null;
    validatedAt: string | null;
    tokenId: string | null;
    source: string | null;
  } | null;
  warnings: string[];
};
