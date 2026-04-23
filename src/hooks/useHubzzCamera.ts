import { Vector3 } from "three";

export const HUBZZ_CAMERA_OFFSET = new Vector3(60, 45, 60);
export const HUBZZ_ORTHO_HALF_HEIGHT = 10;  // d in CameraManager.refresh()
export const HUBZZ_TILE_SIZE = 1.0;
// Bounding box height = 2 tiles = 2.0 world units. Intentionally equals tile width × 2,
// so the box reads as "2 tiles tall" visually. Avatar target height is 1.5–1.75m,
// leaving ~0.25m headroom inside the box for hair / hats / idle head-bob.
export const HUBZZ_SAFE_VOLUME_HEIGHT = 2.0;
// Target avatar height range for QA — outside this range, rig is too tall/short.
export const AVATAR_TARGET_HEIGHT_MIN = 1.5;
export const AVATAR_TARGET_HEIGHT_MAX = 1.75;

// Seat height standards — ALTIICO proposal.
// NOTE: hubzz WorldTile.ts:13 currently defines these as 0.5/1.0/1.5 which are
// ergonomically wrong (floor pillow at 0.5m, chair at 1.0m, stool at 1.5m would
// put an avatar's head at ~2.0m sitting). Altiico uses the corrected values so
// the preview reflects realistic seat positioning. Migrate hubzz to match before
// publishing sit-related assets.
export const HUBZZ_SEAT_HEIGHTS = {
  floor: 0.25,  // floor pillow / cushion — low
  chair: 0.50,  // standard chair / sofa / couch
  stool: 0.75,  // bar stool / counter stool
} as const;

export type SeatHeightStandard = keyof typeof HUBZZ_SEAT_HEIGHTS | 'none';

/**
 * Computes the orthographic frustum parameters for a given aspect ratio,
 * matching the hubzz CameraManager.refresh() formula exactly.
 */
export function computeOrthoFrustum(aspect: number) {
  const d = HUBZZ_ORTHO_HALF_HEIGHT;
  return {
    left: -d * aspect,
    right: d * aspect,
    top: d,
    bottom: -d,
    near: 0.1,
    far: 1000,
  };
}
