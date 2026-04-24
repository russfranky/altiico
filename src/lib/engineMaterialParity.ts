/**
 * Hubzz engine shader pipeline — full parity for altii.co preview.
 *
 * Ported verbatim from packages/client/src/engine/entities/avatar/
 * AvatarVRMManager.ts (assignMaterials + setMaterialProperties, called
 * back-to-back from EntityAvatar.ts:723-727). Goal: altii.co preview
 * renders avatars with the same shader pipeline the in-world game
 * client uses, so "looks fine here" means "looks fine in world."
 *
 * The pipeline, in order:
 *   1. Detect baked single-mesh VRMs (e.g. 100avatars mesh_ava_*.baked)
 *      — these disable outlines entirely to avoid "black head" bug.
 *   2. Resolve per-collection outline config (thickness, enable).
 *   3. Compute smoothed normals on every geometry for clean outline.
 *   4. Name-based face exclusion — skip outline on eye/mouth/teeth/etc.
 *   5. Swap every material to MeshToonMaterial (drops MToon/PBR).
 *   6. Create backside outline SkinnedMesh for each mesh that qualifies.
 *   7. Load /textures/threeTone.jpg and assign as gradientMap.
 *   8. Apply emissiveMap = map, emissiveIntensity = 1.0 on every mat.
 *
 * This is a COPY of engine code. When the engine changes, update here
 * in lockstep (and TODO: extract to @hubzz/avatar-render package).
 */
import {
  BackSide,
  BufferAttribute,
  BufferGeometry,
  Mesh,
  MeshToonMaterial,
  Object3D,
  ShaderMaterial,
  SkinnedMesh,
  TextureLoader,
  Vector3,
} from 'three';

// ── Per-collection outline config (mirror of Config.outline.collections) ─
// When the engine's Config.json changes, update this table so altii.co
// applies the same per-collection overrides.
interface OutlineConfig {
  enabled?: boolean;
  outlineWidth?: number;
  outlineColor?: { r: number; g: number; b: number; alpha: number };
  cacheMaterials?: boolean;
}

const OUTLINE_CONFIG: { default: OutlineConfig; collections: Record<string, OutlineConfig> } = {
  default: {
    enabled: true,
    outlineWidth: 0.004,
    outlineColor: { r: 0, g: 0, b: 0, alpha: 0.8 },
  },
  collections: {
    'retrodoges-1': {
      outlineWidth: 0.002,
      enabled: true,
      outlineColor: { r: 0, g: 0, b: 0, alpha: 0.8 },
    },
  },
};

// ── Outline shaders (verbatim from AvatarVRMManager) ─────────────────────
const OUTLINE_VERT = /* glsl */ `
  #include <common>
  #include <morphtarget_pars_vertex>
  #include <skinning_pars_vertex>
  uniform float thickness;
  void main() {
    #include <beginnormal_vertex>
    #include <morphnormal_vertex>
    #include <skinbase_vertex>
    #include <skinnormal_vertex>
    #include <defaultnormal_vertex>
    #include <begin_vertex>
    #include <morphtarget_vertex>
    #include <skinning_vertex>
    #include <project_vertex>
    vec3 newPos = transformed + normal * thickness;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPos, 1.0);
  }
`;
const OUTLINE_FRAG = /* glsl */ `
  void main() {
    gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
  }
`;

// ── Smoothed normals ─────────────────────────────────────────────────────
// Averages normals at shared vertex positions. Sharp creases (mouth,
// eyelids) keep their originals via dot-product threshold; smooth areas
// fully adopt the group average. Matches AvatarVRMManager.computeSmoothedNormals.
function computeSmoothedNormals(geometry: BufferGeometry): void {
  const posAttr = geometry.attributes.position;
  const normAttr = geometry.attributes.normal;
  if (!posAttr || !normAttr) return;

  const count = posAttr.count;
  const precision = 1000;

  const normalMap = new Map<string, Vector3>();
  for (let i = 0; i < count; i++) {
    const key = `${Math.round(posAttr.getX(i) * precision)},${Math.round(posAttr.getY(i) * precision)},${Math.round(posAttr.getZ(i) * precision)}`;
    if (!normalMap.has(key)) normalMap.set(key, new Vector3());
    normalMap.get(key)!.add(new Vector3(normAttr.getX(i), normAttr.getY(i), normAttr.getZ(i)));
  }
  normalMap.forEach((n) => n.normalize());

  const sharpThreshold = 0.4;
  const smoothThreshold = 0.7;
  const smoothed = new Float32Array(count * 3);
  const orig = new Vector3();
  const avg = new Vector3();

  for (let i = 0; i < count; i++) {
    const key = `${Math.round(posAttr.getX(i) * precision)},${Math.round(posAttr.getY(i) * precision)},${Math.round(posAttr.getZ(i) * precision)}`;
    orig.set(normAttr.getX(i), normAttr.getY(i), normAttr.getZ(i)).normalize();
    avg.copy(normalMap.get(key)!);
    const dot = orig.dot(avg);
    let blend: number;
    if (dot < sharpThreshold) blend = 0;
    else if (dot > smoothThreshold) blend = 1;
    else blend = (dot - sharpThreshold) / (smoothThreshold - sharpThreshold);
    const final = orig.clone().lerp(avg, blend).normalize();
    smoothed[i * 3] = final.x;
    smoothed[i * 3 + 1] = final.y;
    smoothed[i * 3 + 2] = final.z;
  }
  // Engine parity: store as separate `smoothNormal` attribute, leave
  // original `normal` untouched. The engine does the same — no shader in
  // the in-world code actually reads smoothNormal, but it's preserved in
  // case a future shader does. Writing to `normal` directly (an earlier
  // iteration) caused material tearing because MeshToonMaterial's
  // shade-gradient lighting is sensitive to normal-buffer smoothing
  // introducing flat facets at the group boundaries.
  geometry.setAttribute('smoothNormal', new BufferAttribute(smoothed, 3));
}

// ── Face-exclusion filter ────────────────────────────────────────────────
const FACE_EXCLUDE_TOKENS = [
  'mouth', 'oral', 'teeth', 'tongue', 'tooth', 'gum',
  'eye', 'iris', 'pupil', 'brow', 'lash', 'nose',
];
function isFaceFeature(name: string): boolean {
  const n = name.toLowerCase();
  return FACE_EXCLUDE_TOKENS.some((t) => n.includes(t));
}

// ── Main entry: full engine pipeline ─────────────────────────────────────
export interface EngineMaterialOptions {
  /** Collection slug for per-set outline override. Optional. */
  collection?: string;
  /** Matches world.entityScale.x at line 557. Defaults to 1 (rooftop). */
  entityScale?: number;
  /** Disable the whole pipeline (somnia bypass). */
  somnia?: boolean;
}

export function applyEngineMaterialOverrides(
  root: Object3D,
  opts: EngineMaterialOptions = {},
): void {
  if (opts.somnia) return;

  // ── Baked single-mesh detection ────────────────────────────────────────
  let meshCount = 0;
  let hasBakedMeshName = false;
  root.traverse((child) => {
    if (child instanceof Mesh) {
      meshCount++;
      const lower = child.name.toLowerCase();
      if (lower.includes('.baked') || lower.includes('_baked')) {
        hasBakedMeshName = true;
      }
    }
  });
  const isBakedSingleMesh = meshCount === 1 || hasBakedMeshName;

  // ── Resolve outline config ─────────────────────────────────────────────
  const collectionConfig = opts.collection
    ? OUTLINE_CONFIG.collections[opts.collection] ?? null
    : null;
  const outlineEnabled =
    !isBakedSingleMesh && (collectionConfig ? collectionConfig.enabled !== false : true);
  const baseThickness = collectionConfig?.outlineWidth ?? OUTLINE_CONFIG.default.outlineWidth ?? 0.004;
  const entityScale = opts.entityScale ?? 1;
  const outlineThickness = baseThickness * entityScale;

  // ── Smoothed normals + face exclusion tagging ─────────────────────────
  root.traverse((child) => {
    if (child instanceof Mesh && child.geometry) {
      computeSmoothedNormals(child.geometry);
      if (!outlineEnabled) {
        (child as any).userData.noOutline = true;
        return;
      }
      if (isFaceFeature(child.name)) {
        (child as any).userData.noOutline = true;
      }
    }
  });

  // ── MeshToonMaterial swap + outline hull creation ─────────────────────
  const outlineChildren: SkinnedMesh[] = [];

  const swapMat = (child: Mesh, mat: any) => {
    const matName = (mat.name || '').toLowerCase();
    const childName = (child.name || '').toLowerCase();
    const isGlasses = matName.includes('glasses') || childName.includes('glasses');
    if (isGlasses) {
      mat.userData.outlineParameters = { visible: false };
      return;
    }

    const toonMat = new MeshToonMaterial({
      color: mat.color,
      map: mat.map,
      transparent: mat.transparent,
      opacity: mat.opacity,
    });
    child.material = toonMat;

    if (child instanceof SkinnedMesh && !child.userData.noOutline) {
      const outlineMat = new ShaderMaterial({
        vertexShader: OUTLINE_VERT,
        fragmentShader: OUTLINE_FRAG,
        uniforms: { thickness: { value: outlineThickness } },
        side: BackSide,
      });
      const outlineMesh = new SkinnedMesh(child.geometry, outlineMat);
      outlineMesh.bind(child.skeleton, child.bindMatrix);
      outlineMesh.renderOrder = child.renderOrder - 1;
      outlineMesh.frustumCulled = false;
      (outlineMesh as any).userData.noOutline = true;
      child.parent!.add(outlineMesh);
      outlineChildren.push(outlineMesh);
    }

    (child as any).userData.noOutline = true;
  };

  root.traverse((child) => {
    if (child instanceof Mesh) {
      const mat = Array.isArray(child.material) ? child.material[0] : child.material;
      if (mat) swapMat(child, mat);
    }
  });

  // ── Load tone gradient and assign to every swapped MeshToonMaterial ────
  const loader = new TextureLoader();
  loader.load('/textures/threeTone.jpg', (texture) => {
    root.traverse((child) => {
      if (child instanceof Mesh && child.material instanceof MeshToonMaterial) {
        (child.material as MeshToonMaterial).gradientMap = texture;
        (child.material as MeshToonMaterial).needsUpdate = true;
      }
    });
  });

  // ── setMaterialProperties: emissive hack ──────────────────────────────
  const apply = (m: any) => {
    m.emissiveMap = m.map;
    m.emissiveIntensity = 1.0;
    if (m.isOutline) m.outlineWidthFactor = 0;
  };
  root.traverse((child: any) => {
    if (!child.material) return;
    if (Array.isArray(child.material)) child.material.forEach(apply);
    else apply(child.material);
  });
}
