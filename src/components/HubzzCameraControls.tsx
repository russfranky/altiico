/**
 * HubzzCameraControls — replaces OrbitControls in IsometricCanvas.
 *
 * Matches hubzz CameraManager + InputManager behavior exactly:
 *   - Scroll wheel: zoom between [0.3, 3.0], cursor-centered
 *   - Left-click drag on empty space: pan camera (no rotation ever)
 *   - Middle-click drag: also pan
 *   - No rotation — camera orientation is locked to canonical isometric vector
 *
 * Pan math ported from hubzz InputManager.panLeft / panUp (InputManager.ts:947-980).
 * Column 0 of the camera matrix = right vector. Column 1 = up vector.
 * Y component zeroed + renormalized so pan stays horizontal on the XZ ground plane.
 * Column 1 Y is multiplied by 2 (matching hubzz panUp's `distance * 2` multiplier).
 *
 * This component is a THREE.js hook component — it must be rendered inside <Canvas>.
 * It does NOT render any geometry.
 *
 * Imperative handle: resetCamera() — resets position + zoom to canonical defaults.
 */

import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { HUBZZ_CAMERA_OFFSET } from '@/hooks/useHubzzCamera';

const ZOOM_MIN = 0.3;
const ZOOM_MAX = 3.0;
const ZOOM_SENSITIVITY = 0.001; // matches hubzz zoomSensitivity in config

export interface HubzzCameraControlsHandle {
  resetCamera(): void;
}

interface HubzzCameraControlsProps {
  /**
   * If true, the pointer-down on the canvas is being consumed by the avatar
   * drag system and camera pan should NOT activate. Set to true when avatar
   * drag is active; false otherwise.
   */
  panBlocked?: boolean;
}

const HubzzCameraControls = forwardRef<HubzzCameraControlsHandle, HubzzCameraControlsProps>(
  function HubzzCameraControls({ panBlocked = false }, ref) {
    const { camera, gl } = useThree();
    const panBlockedRef = useRef(panBlocked);
    panBlockedRef.current = panBlocked;

    useImperativeHandle(ref, () => ({
      resetCamera() {
        if (!(camera instanceof THREE.OrthographicCamera)) return;
        camera.position.copy(HUBZZ_CAMERA_OFFSET);
        camera.zoom = 1.0;
        camera.lookAt(0, 0, 0);
        camera.updateProjectionMatrix();
      },
    }));

    useEffect(() => {
      if (!(camera instanceof THREE.OrthographicCamera)) return;
      const canvas = gl.domElement;

      // --- Pan state ---
      let isPanning = false;
      let panLastX = 0;
      let panLastY = 0;
      // middle-click also pans
      const isPanButton = (b: number) => b === 0 || b === 1;

      const onPointerDown = (e: PointerEvent) => {
        if (!isPanButton(e.button)) return;
        if (panBlockedRef.current) return; // avatar drag owns this pointer
        isPanning = true;
        panLastX = e.clientX;
        panLastY = e.clientY;
        canvas.setPointerCapture(e.pointerId);
      };

      const onPointerMove = (e: PointerEvent) => {
        if (!isPanning) return;
        const dx = e.clientX - panLastX;
        const dy = e.clientY - panLastY;
        panLastX = e.clientX;
        panLastY = e.clientY;

        // Pan math — port of hubzz InputManager.panLeft / panUp (InputManager.ts:947-980)
        // panLeft: column 0 of camera matrix, zero Y, normalize, multiply by -distance
        // panUp:   column 1 of camera matrix, zero Y, normalize, multiply by +distance*2
        // In altiico there is no separate targetObject; we move camera.position directly.
        const mat = camera.matrix;
        const aspect = canvas.clientWidth;
        const height = canvas.clientHeight;

        // Horizontal pan (screen X → world XZ)
        const distLeft = dx * (camera.right - camera.left) / camera.zoom / aspect;
        const vLeft = new THREE.Vector3();
        vLeft.setFromMatrixColumn(mat, 0);
        vLeft.y = 0;
        vLeft.normalize();
        vLeft.multiplyScalar(-distLeft);

        // Vertical pan (screen Y → world XZ, using column 1 flattened)
        const distUp = dy * (camera.top - camera.bottom) / camera.zoom / height;
        const vUp = new THREE.Vector3();
        vUp.setFromMatrixColumn(mat, 1);
        vUp.y = 0;
        vUp.normalize();
        vUp.multiplyScalar(distUp * 2);

        camera.position.add(vLeft).add(vUp);
        camera.updateProjectionMatrix();
      };

      const onPointerUp = (e: PointerEvent) => {
        if (!isPanning) return;
        isPanning = false;
        try { canvas.releasePointerCapture(e.pointerId); } catch { /* ignored */ }
      };

      const onPointerCancel = (e: PointerEvent) => {
        isPanning = false;
        try { canvas.releasePointerCapture(e.pointerId); } catch { /* ignored */ }
      };

      // --- Zoom ---
      const onWheel = (e: WheelEvent) => {
        e.preventDefault();
        if (!(camera instanceof THREE.OrthographicCamera)) return;

        // Cursor-relative zoom — same approach as hubzz InputManager wheel handler.
        // Compute world point under cursor before zooming, then offset camera so the
        // world point stays under the cursor after zooming.
        const rect = canvas.getBoundingClientRect();
        const ndcX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        const ndcY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        // World position under cursor at current zoom
        const halfW = (camera.right - camera.left) / 2 / camera.zoom;
        const halfH = (camera.top - camera.bottom) / 2 / camera.zoom;

        // Camera looks along -Z in its local space; the cursor maps to camera's XY plane.
        // The "before" world position offset from camera center:
        const beforeX = ndcX * halfW;
        const beforeY = ndcY * halfH;

        // Apply zoom
        const zoomFactor = Math.exp(-e.deltaY * ZOOM_SENSITIVITY);
        camera.zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, camera.zoom * zoomFactor));
        camera.updateProjectionMatrix();

        // "After" world position — shift camera so cursor stays fixed
        const afterHalfW = (camera.right - camera.left) / 2 / camera.zoom;
        const afterHalfH = (camera.top - camera.bottom) / 2 / camera.zoom;
        const afterX = ndcX * afterHalfW;
        const afterY = ndcY * afterHalfH;

        // Camera's right vector (column 0) and up vector (column 1) in world space
        const mat = camera.matrix;
        const right = new THREE.Vector3().setFromMatrixColumn(mat, 0);
        const up = new THREE.Vector3().setFromMatrixColumn(mat, 1);

        // Shift camera by the delta so the world point under the cursor stays fixed
        const dX = beforeX - afterX;
        const dY = beforeY - afterY;
        camera.position.addScaledVector(right, dX);
        camera.position.addScaledVector(up, dY);
        camera.updateProjectionMatrix();
      };

      canvas.addEventListener('pointerdown', onPointerDown);
      canvas.addEventListener('pointermove', onPointerMove);
      canvas.addEventListener('pointerup', onPointerUp);
      canvas.addEventListener('pointercancel', onPointerCancel);
      canvas.addEventListener('wheel', onWheel, { passive: false });

      return () => {
        canvas.removeEventListener('pointerdown', onPointerDown);
        canvas.removeEventListener('pointermove', onPointerMove);
        canvas.removeEventListener('pointerup', onPointerUp);
        canvas.removeEventListener('pointercancel', onPointerCancel);
        canvas.removeEventListener('wheel', onWheel);
      };
    }, [camera, gl]);

    return null;
  },
);

export default HubzzCameraControls;
