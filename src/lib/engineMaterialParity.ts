/**
 * Hubzz engine material parity for altii.co preview.
 *
 * The hubzz in-world client modifies every VRM material on load:
 *   m.emissiveMap = m.map;
 *   m.emissiveIntensity = 1.0;
 *   if (m.isOutline) m.outlineWidthFactor = 0;
 *
 * This is an "unlit look" hack — it binds the diffuse map to the emissive
 * slot so avatars render flat/bright regardless of scene lighting. It has
 * bugs (MToon materials without m.map render black, spec-default fields
 * stripped by the optimizer cause partial black blobs), but it IS what
 * ships to users today.
 *
 * For altii.co to be a useful QA tool, its preview must render avatars
 * with byte-identical material behaviour to the in-world engine. Any
 * divergence = "looks fine in preview, broken in world" silent failures.
 *
 * This module is the single place every VRM-loading surface in altiico
 * calls immediately after VRMUtils.rotateVRM0(). When the engine shader
 * path changes (Phase 2), update this function in lockstep. Long-term,
 * extract to a shared @hubzz/avatar-render npm package so both repos
 * import the same code.
 *
 * Source: packages/client/src/engine/entities/avatar/AvatarVRMManager.ts:351
 */
import type { Object3D } from 'three';

export function applyEngineMaterialOverrides(root: Object3D): void {
  const apply = (m: any) => {
    m.emissiveMap = m.map;
    m.emissiveIntensity = 1.0;
    if (m.isOutline) m.outlineWidthFactor = 0;
  };

  root.traverse((child: any) => {
    if (!child.material) return;
    if (Array.isArray(child.material)) {
      child.material.forEach(apply);
    } else {
      apply(child.material);
    }
  });
}
