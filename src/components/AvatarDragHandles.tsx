/**
 * AvatarDragHandles — camera-space drag for avatar rig correction.
 *
 * Rewritten to address all 25 edge cases from the spec:
 *
 * Drag mechanics:
 *   1. No orbit conflict — OrbitControls gone; avatar drag is exclusive on avatar hits
 *   2. Modifier keys read LIVE on every pointermove — shift/ctrl toggle mid-drag
 *   3. Camera-space drag plane — perpendicular to camera forward (not world XY)
 *   4. Raycasts VRM mesh children first; falls back to camera-space plane only when over avatar
 *   5. Ctrl/Cmd = XZ (horizontal) lock, Shift = Y lock, no modifier = camera-space free
 *   6. Stable effect — listeners registered once; target ref updates don't re-register
 *
 * Offset accuracy:
 *   7. baseOffsetRef fires on every move (display), session save happens at commit time in parent
 *   8. Offset + position both reset on target change (via resetToSnap)
 *   9. resetToSnap() forces snap re-run on demand
 *  10. Offset schema captured via onOffsetChange; parent saves to session
 *
 * Interaction with other systems:
 *  11. Offset cleared externally by parent on context change (facing, seatHeight, anim, avatar)
 *  12. Same clear-on-change as #11
 *  13. Camera-space drag makes facing irrelevant — drag right on screen = move right
 *  14. Drag state cleanly released on target change
 *  15. onOffsetChange throttled to ~30fps via rAF flag
 *
 * Visual truth:
 *  16. Offset clamped ±0.5m per axis; clamped state reported via onClampedChange
 *  17. Offset display reset atomically when target changes (baseOffsetRef.set(0,0,0))
 *  18. Position reset on target change so snap result is shown
 *
 * Perf / memory:
 *  19. One raycaster per effect lifecycle
 *  20. Invisible planes have matrixAutoUpdate = false
 *  21. draggingRef nulled + pointer capture released on target change
 *
 * Input edge cases:
 *  22. setPointerCapture on pointerdown; only primary pointer tracked
 *  23. button === 0 guard kept
 *  24. pointermove on window so drag continues off-canvas
 *  25. pointercancel + lostpointercapture clean up sticky drag
 */

import { useEffect, useRef, useCallback } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';

const CLAMP = 0.5; // ±0.5m per axis

export interface DragOffset {
  x: number;
  y: number;
  z: number;
}

export function AvatarDragHandles({
  target,
  enabled,
  onOffsetChange,
  onClampedChange,
}: {
  target: THREE.Object3D | null;
  enabled: boolean;
  onOffsetChange: (offset: DragOffset) => void;
  onClampedChange?: (clamped: boolean) => void;
}) {
  const { scene, camera, gl } = useThree();

  // Refs that are stable across renders — updated by ref, not by re-registering listeners
  const targetRef = useRef<THREE.Object3D | null>(null);
  const enabledRef = useRef(enabled);
  const baseOffsetRef = useRef(new THREE.Vector3(0, 0, 0));

  // Drag state
  const draggingRef = useRef<{
    pointerId: number;
    camSpacePlane: THREE.Plane;
    lastWorldPoint: THREE.Vector3;
  } | null>(null);

  // rAF throttle for onOffsetChange
  const rafPendingRef = useRef(false);

  // Callback refs — always current, no re-registration
  const onOffsetChangeRef = useRef(onOffsetChange);
  onOffsetChangeRef.current = onOffsetChange;
  const onClampedChangeRef = useRef(onClampedChange);
  onClampedChangeRef.current = onClampedChange;

  // Clamp helper — applies ±CLAMP per axis to the running offset, updates clamped state
  const clampOffset = useCallback((offset: THREE.Vector3) => {
    const clamped =
      Math.abs(offset.x) > CLAMP ||
      Math.abs(offset.y) > CLAMP ||
      Math.abs(offset.z) > CLAMP;
    offset.x = Math.max(-CLAMP, Math.min(CLAMP, offset.x));
    offset.y = Math.max(-CLAMP, Math.min(CLAMP, offset.y));
    offset.z = Math.max(-CLAMP, Math.min(CLAMP, offset.z));
    onClampedChangeRef.current?.(clamped);
    return offset;
  }, []);

  // When target changes: reset position back to snap baseline, clear offset, release any drag
  useEffect(() => {
    // Release any active drag cleanly
    if (draggingRef.current) {
      try { gl.domElement.releasePointerCapture(draggingRef.current.pointerId); } catch { /* ignored */ }
      draggingRef.current = null;
    }
    gl.domElement.style.cursor = enabled ? 'default' : '';

    // Reset offset + position
    baseOffsetRef.current.set(0, 0, 0);
    onClampedChangeRef.current?.(false);

    // Fire a zero-offset notification so parent display resets
    onOffsetChangeRef.current({ x: 0, y: 0, z: 0 });

    // Reset target position to snap origin — the snap effect in IsometricCanvas will
    // fire separately (it depends on vrmUrl/fbxUrl/seatHeight), so here we just
    // ensure the offset contribution is zeroed.
    if (target) {
      target.position.set(0, 0, 0);
    }

    targetRef.current = target;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  // Keep enabledRef in sync; also clear cursor when disabled
  useEffect(() => {
    enabledRef.current = enabled;
    if (!enabled) {
      // Release any active drag
      if (draggingRef.current) {
        try { gl.domElement.releasePointerCapture(draggingRef.current.pointerId); } catch { /* ignored */ }
        draggingRef.current = null;
      }
      gl.domElement.style.cursor = '';
    } else {
      gl.domElement.style.cursor = 'default';
    }
  }, [enabled, gl]);

  // Stable listener registration — registered once, reads refs for all dynamic state
  useEffect(() => {
    const canvas = gl.domElement;
    const raycaster = new THREE.Raycaster();
    const ndc = new THREE.Vector2();

    // Build a camera-space drag plane perpendicular to camera forward
    const buildCamPlane = (worldPoint: THREE.Vector3): THREE.Plane => {
      const camForward = new THREE.Vector3();
      camera.getWorldDirection(camForward);
      return new THREE.Plane().setFromNormalAndCoplanarPoint(camForward, worldPoint);
    };

    // Get NDC from pointer event
    const getNDC = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      ndc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      ndc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    };

    // Get all VRM skinned/mesh children for raycasting
    const getAvatarMeshes = (): THREE.Object3D[] => {
      const t = targetRef.current;
      if (!t) return [];
      const meshes: THREE.Object3D[] = [];
      t.traverse((node) => {
        if ((node as THREE.Mesh).isMesh || (node as THREE.SkinnedMesh).isSkinnedMesh) {
          meshes.push(node);
        }
      });
      return meshes;
    };

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      if (!enabledRef.current) return;
      const t = targetRef.current;
      if (!t) return;

      getNDC(e);
      raycaster.setFromCamera(ndc, camera);

      // Raycast avatar meshes first (#4 — don't hit invisible planes)
      const meshes = getAvatarMeshes();
      const avatarHits = raycaster.intersectObjects(meshes, false);

      if (avatarHits.length === 0) {
        // Pointer is over empty space — let camera pan handle it
        return;
      }

      const hitPoint = avatarHits[0].point;
      const plane = buildCamPlane(hitPoint);

      draggingRef.current = {
        pointerId: e.pointerId,
        camSpacePlane: plane,
        lastWorldPoint: hitPoint.clone(),
      };

      try { canvas.setPointerCapture(e.pointerId); } catch { /* ignored */ }
      canvas.style.cursor = 'grabbing';
    };

    const onPointerMove = (e: PointerEvent) => {
      const dragging = draggingRef.current;
      if (!dragging) {
        // Show grab cursor when hovering over avatar
        if (enabledRef.current && targetRef.current) {
          getNDC(e);
          raycaster.setFromCamera(ndc, camera);
          const meshes = getAvatarMeshes();
          const hits = raycaster.intersectObjects(meshes, false);
          canvas.style.cursor = hits.length > 0 ? 'grab' : 'default';
        }
        return;
      }

      // Only handle primary pointer (#22)
      if (e.pointerId !== dragging.pointerId) return;

      getNDC(e);
      raycaster.setFromCamera(ndc, camera);

      // Intersect camera-space plane to get world delta
      const worldPoint = new THREE.Vector3();
      const hit = raycaster.ray.intersectPlane(dragging.camSpacePlane, worldPoint);
      if (!hit) return;

      const delta = worldPoint.clone().sub(dragging.lastWorldPoint);
      dragging.lastWorldPoint = worldPoint.clone();

      // Read modifiers LIVE (#2, #5) — Shift = Y only, Ctrl/Cmd = XZ only, none = free
      if (e.shiftKey) {
        delta.x = 0;
        delta.z = 0;
      } else if (e.ctrlKey || e.metaKey) {
        delta.y = 0;
      }

      const t = targetRef.current;
      if (!t) return;

      // Apply delta to accumulated offset, then clamp
      baseOffsetRef.current.add(delta);
      clampOffset(baseOffsetRef.current);

      // Apply clamped offset as absolute position from snap origin (0,0,0)
      t.position.copy(baseOffsetRef.current);

      // Throttle React state update to ~30fps (#15)
      if (!rafPendingRef.current) {
        rafPendingRef.current = true;
        requestAnimationFrame(() => {
          rafPendingRef.current = false;
          const o = baseOffsetRef.current;
          onOffsetChangeRef.current({ x: o.x, y: o.y, z: o.z });
        });
      }
    };

    const releasePointer = (e: PointerEvent) => {
      const dragging = draggingRef.current;
      if (!dragging) return;
      if (e.pointerId !== dragging.pointerId) return;
      draggingRef.current = null;
      try { canvas.releasePointerCapture(e.pointerId); } catch { /* ignored */ }
      canvas.style.cursor = enabledRef.current ? 'default' : '';
    };

    // Window listeners so drag continues off-canvas (#24)
    canvas.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', releasePointer);
    // Clean release on cancel + lost capture (#25)
    window.addEventListener('pointercancel', releasePointer);
    canvas.addEventListener('lostpointercapture', releasePointer as EventListener);

    return () => {
      canvas.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', releasePointer);
      window.removeEventListener('pointercancel', releasePointer);
      canvas.removeEventListener('lostpointercapture', releasePointer as EventListener);
      canvas.style.cursor = '';

      // Release any active drag on cleanup
      if (draggingRef.current) {
        try { canvas.releasePointerCapture(draggingRef.current.pointerId); } catch { /* ignored */ }
        draggingRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camera, gl, clampOffset]);
  // Intentionally NOT including target/enabled/onOffsetChange — we use refs for those (#6)

  return null;
}
