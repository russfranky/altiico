export interface PropDefinition {
  id: string;
  name: string;
  url: string;
  category: string;
  defaultOffset: { x: number; y: number; z: number };
  defaultRotY: number;
}

export interface PropManifest {
  props: PropDefinition[];
}

// Instance = "this prop with these placement overrides, currently active in the scene"
export interface PropInstance {
  definition: PropDefinition;
  offset: { x: number; y: number; z: number };
  rotY: number;
}
