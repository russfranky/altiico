export interface CollectionOpensource {
  repo?: string;
  original?: string;
  release?: string;
  sketchfabR1?: string;
  sketchfabR2?: string;
  caWorld?: string;
  avatarGarden?: string;
  registry?: string;
  projectsJson?: string;
}

export interface Collection {
  name: string;
  items: string;
  banner: string;
  pfp: string;
  assets3D: string;
  category: string;
  contract?: string;
  description?: string;
  license?: string;
  slug?: string;
  metadataParam?: string;
  opensource?: CollectionOpensource;
}

export interface AvatarStats {
  triangles?: number;
  meshes?: number;
  fileSize?: number;
  fileSizeOptimized?: number;
}

export interface Avatar {
  id: number;
  name: string;
  collection: string;
  image: string;
  vrm: string;
  vrmUrl?: string;
  interop?: string[];
  opensea: string;
  traits?: Record<string, string>;
  stats?: AvatarStats;
  license?: string;
  source?: 'static' | 'api';
}
