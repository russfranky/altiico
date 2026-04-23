import * as THREE from 'three';

// ── Outline vertex shader ─────────────────────────────────────────
// Single-pass: rendered as geometry group 1 on each mesh (BackSide).
// Includes full skinning support so outline follows animation correctly.
// creaseFactor suppresses outline on smooth interior surfaces.
const OUTLINE_VERTEX_SHADER = [
  '#include <common>',
  '#include <uv_pars_vertex>',
  '#include <displacementmap_pars_vertex>',
  '#include <fog_pars_vertex>',
  '#include <morphtarget_pars_vertex>',
  '#include <skinning_pars_vertex>',
  '#include <logdepthbuf_pars_vertex>',
  '#include <clipping_planes_pars_vertex>',

  'attribute vec3 smoothNormal;',
  'uniform float outlineThickness;',
  'uniform vec3 outlineCameraPosition;',
  'varying float depthAlpha;',

  'vec4 calculateOutline(vec4 pos, vec3 normal, vec4 skinned, float creaseFactor) {',
  '  float depth = length(outlineCameraPosition - skinned.xyz);',
  '  float depthRatio = clamp(1.0 / depth, 0.1, 1.0) * 8.5;',
  '  float angleFactor = dot(normalize(outlineCameraPosition - skinned.xyz), normalize(normal));',
  '  float thickness = outlineThickness * depthRatio * ((1.0 - clamp(angleFactor, 0.1, 1.0)) * 1.25);',
  '  thickness *= creaseFactor;',
  '  vec4 pos2 = projectionMatrix * modelViewMatrix * vec4(skinned.xyz + normal, 1.0);',
  '  vec4 norm = normalize(pos - pos2);',
  '  depthAlpha = thickness * 240.0;',
  '  return pos + norm * thickness * pos.w;',
  '}',

  'void main() {',
  '  #include <uv_vertex>',
  '  #include <beginnormal_vertex>',
  '  #include <morphnormal_vertex>',
  '  #include <skinbase_vertex>',
  '  #include <skinnormal_vertex>',
  '  #include <begin_vertex>',
  '  #include <morphtarget_vertex>',
  '  #include <skinning_vertex>',
  '  #include <displacementmap_vertex>',
  '  #include <project_vertex>',
  '  vec3 outlineNormal = length(smoothNormal) > 0.0 ? -smoothNormal : -objectNormal;',
  '  float creaseDot = length(smoothNormal) > 0.0 ? dot(normalize(smoothNormal), normalize(objectNormal)) : 1.0;',
  '  float creaseFactor = creaseDot < 0.5 ? 0.0 : smoothstep(0.5, 0.9, creaseDot);',
  '  gl_Position = calculateOutline(gl_Position, outlineNormal, vec4(transformed, 1.0), creaseFactor);',
  '  #include <logdepthbuf_vertex>',
  '  #include <clipping_planes_vertex>',
  '  #include <fog_vertex>',
  '}',
].join('\n');

const OUTLINE_FRAGMENT_SHADER = [
  '#include <common>',
  '#include <fog_pars_fragment>',
  '#include <logdepthbuf_pars_fragment>',
  '#include <clipping_planes_pars_fragment>',
  'uniform vec3 outlineColor;',
  'uniform float outlineAlpha;',
  'varying float depthAlpha;',
  'void main() {',
  '  #include <clipping_planes_fragment>',
  '  #include <logdepthbuf_fragment>',
  '  gl_FragColor = vec4(outlineColor, outlineAlpha * depthAlpha);',
  '  #include <tonemapping_fragment>',
  '  #include <colorspace_fragment>',
  '  #include <fog_fragment>',
  '  #include <premultiplied_alpha_fragment>',
  '}',
].join('\n');

// ── Smoothed normals ─────────────────────────────────────────────
// Quantizes vertex positions, averages normals at shared positions,
// then blends toward the average based on dot-product thresholds.
// Writes a `smoothNormal` attribute used by the outline shader to
// suppress outline on smooth interior surfaces (crease suppression).
function computeSmoothedNormals(geometry: THREE.BufferGeometry): void {
  const posAttr = geometry.attributes.position;
  const normAttr = geometry.attributes.normal;
  if (!posAttr || !normAttr) return;

  const count = posAttr.count;
  const p = 1000;
  const map = new Map<string, THREE.Vector3>();

  for (let i = 0; i < count; i++) {
    const k = `${Math.round(posAttr.getX(i) * p)},${Math.round(posAttr.getY(i) * p)},${Math.round(posAttr.getZ(i) * p)}`;
    if (!map.has(k)) map.set(k, new THREE.Vector3());
    map.get(k)!.add(new THREE.Vector3(normAttr.getX(i), normAttr.getY(i), normAttr.getZ(i)));
  }
  map.forEach(n => n.normalize());

  const sharp = 0.4, smooth = 0.7;
  const out = new Float32Array(count * 3);
  const orig = new THREE.Vector3(), avg = new THREE.Vector3();

  for (let i = 0; i < count; i++) {
    const k = `${Math.round(posAttr.getX(i) * p)},${Math.round(posAttr.getY(i) * p)},${Math.round(posAttr.getZ(i) * p)}`;
    orig.set(normAttr.getX(i), normAttr.getY(i), normAttr.getZ(i)).normalize();
    avg.copy(map.get(k)!);
    const dot = orig.dot(avg);
    const blend = Math.max(0, Math.min(1, (dot - sharp) / (smooth - sharp)));
    out[i * 3]     = orig.x + (avg.x - orig.x) * blend;
    out[i * 3 + 1] = orig.y + (avg.y - orig.y) * blend;
    out[i * 3 + 2] = orig.z + (avg.z - orig.z) * blend;
    const len = Math.sqrt(out[i * 3] ** 2 + out[i * 3 + 1] ** 2 + out[i * 3 + 2] ** 2);
    if (len > 0) { out[i * 3] /= len; out[i * 3 + 1] /= len; out[i * 3 + 2] /= len; }
  }

  geometry.setAttribute('smoothNormal', new THREE.BufferAttribute(out, 3));
}

/**
 * Creates a gradient texture for MeshToonMaterial (discrete shading steps).
 * @param steps Number of discrete shading steps (default: 5)
 */
export function createToonGradientTexture(steps = 5): THREE.DataTexture {
  const data = new Uint8Array(steps * 4);
  for (let i = 0; i < steps; i++) {
    const v = Math.round((i / Math.max(1, steps - 1)) * 255);
    data[i * 4] = v;
    data[i * 4 + 1] = v;
    data[i * 4 + 2] = v;
    data[i * 4 + 3] = 255;
  }
  const tex = new THREE.DataTexture(data, steps, 1);
  tex.needsUpdate = true;
  tex.minFilter = THREE.NearestFilter;
  tex.magFilter = THREE.NearestFilter;
  tex.wrapS = THREE.ClampToEdgeWrapping;
  return tex;
}

/**
 * Applies toon shading + custom outline to a VRM scene.
 *
 * Each mesh gets two geometry groups:
 *   group 0 — MeshToonMaterial (surface)
 *   group 1 — shared ShaderMaterial, BackSide, with skinning + crease suppression (outline)
 *
 * The returned ShaderMaterial must have its `outlineCameraPosition` uniform
 * updated every frame: `mat.uniforms.outlineCameraPosition.value.copy(camera.position)`
 *
 * @param object3D  Root VRM scene object
 * @param gradientMap  Gradient texture from createToonGradientTexture()
 * @param cameraPosition  Initial camera position for outline uniforms
 * @returns The shared outline ShaderMaterial (update uniforms per frame), or null on empty scene
 */
export function applyToonShader(
  object3D: THREE.Object3D,
  gradientMap: THREE.Texture,
  cameraPosition: THREE.Vector3 = new THREE.Vector3(0, 0, 5),
): THREE.ShaderMaterial | null {
  const sharedOutlineMat = new THREE.ShaderMaterial({
    uniforms: {
      outlineThickness:      { value: 0.002 },
      outlineColor:          { value: new THREE.Color(0, 0, 0) },
      outlineAlpha:          { value: 0.8 },
      outlineCameraPosition: { value: cameraPosition.clone() },
    },
    vertexShader:   OUTLINE_VERTEX_SHADER,
    fragmentShader: OUTLINE_FRAGMENT_SHADER,
    side: THREE.BackSide,
    transparent: true,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  });

  let applied = false;

  object3D.traverse((node) => {
    if (!(node instanceof THREE.Mesh) || !node.material || !node.geometry) return;

    const name = (node.name || '').toLowerCase();
    const noOutline = ['mouth', 'oral', 'teeth', 'tongue', 'tooth', 'gum'].some(w => name.includes(w));

    const mats = Array.isArray(node.material) ? node.material : [node.material];
    const surf = mats[0] as THREE.MeshStandardMaterial;
    if (!surf) return;

    const isGlasses = (surf.name || name).toLowerCase().includes('glasses');

    const toonMat = isGlasses ? surf : (() => {
      const t = new THREE.MeshToonMaterial({
        color: surf.color?.clone() ?? new THREE.Color(0xffffff),
        map: surf.map ?? null,
        transparent: surf.transparent ?? false,
        opacity: surf.opacity ?? 1,
        gradientMap,
      });
      // Boost vibrancy: use diffuse map as emissive so shadows are tinted, not grey
      if (surf.map) {
        t.emissiveMap = surf.map;
        t.emissiveIntensity = 1.0;
      }
      return t;
    })();

    if (noOutline || isGlasses) {
      node.material = toonMat;
      node.geometry.clearGroups();
      return;
    }

    // Compute smoothed normals for crease suppression in outline shader
    computeSmoothedNormals(node.geometry);

    // Two geometry groups: group 0 = surface toon, group 1 = outline (BackSide)
    const drawCount = node.geometry.index
      ? node.geometry.index.count
      : (node.geometry.attributes.position?.count ?? 0);
    node.geometry.clearGroups();
    node.geometry.addGroup(0, drawCount, 0);
    node.geometry.addGroup(0, drawCount, 1);

    node.material = [toonMat, sharedOutlineMat];
    applied = true;
  });

  return applied ? sharedOutlineMat : null;
}

/**
 * Disposes of a Three.js object and all its children, freeing GPU memory.
 */
export function disposeScene(obj: THREE.Object3D | null): void {
  if (!obj) return;

  obj.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((m: THREE.Material) => {
          for (const key in m) {
            const value = (m as Record<string, unknown>)[key];
            if (value && typeof (value as { dispose?: unknown }).dispose === 'function') {
              (value as { dispose: () => void }).dispose();
            }
          }
          m.dispose();
        });
      }
    }
  });
}
