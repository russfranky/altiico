import { useEffect, useRef } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { PropInstance } from '@/lib/propsTypes';
import { applyToonShader, createToonGradientTexture } from '@/lib/threeUtils';

// Shared gradient for all props — single 5-step toon ramp
const sharedGradientMap = createToonGradientTexture(5);

/**
 * Renders zero or more props into the scene from a list of PropInstance.
 * Props are placed in tile-unit coordinates — x/z are multiplied by HUBZZ_TILE_SIZE (1.0).
 * Each prop is its own top-level object parented to scene; swapped wholesale on list change
 * (simpler than incremental diffing; N is expected to be small — 1-10).
 */
export function PropLayer({ instances }: { instances: PropInstance[] }) {
  const { scene, camera } = useThree();
  const loadedRef = useRef<Map<string, THREE.Group>>(new Map());
  const outlineMatsRef = useRef<Map<string, THREE.ShaderMaterial>>(new Map());

  // Keep the outline shader's outlineCameraPosition uniform in sync each frame
  useFrame(() => {
    for (const mat of outlineMatsRef.current.values()) {
      mat.uniforms.outlineCameraPosition.value.copy(camera.position);
    }
  });

  useEffect(() => {
    const currentIds = new Set(instances.map((i) => i.definition.id));

    // Remove props that are no longer in the active list
    for (const [id, obj] of loadedRef.current.entries()) {
      if (!currentIds.has(id)) {
        scene.remove(obj);
        obj.traverse((n) => {
          if ((n as THREE.Mesh).isMesh) {
            (n as THREE.Mesh).geometry?.dispose();
            const mat = (n as THREE.Mesh).material;
            if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
            else mat?.dispose();
          }
        });
        outlineMatsRef.current.get(id)?.dispose();
        outlineMatsRef.current.delete(id);
        loadedRef.current.delete(id);
      }
    }

    // Add or update props
    instances.forEach(async (inst) => {
      const existing = loadedRef.current.get(inst.definition.id);
      if (existing) {
        existing.position.set(inst.offset.x, inst.offset.y, inst.offset.z);
        existing.rotation.y = inst.rotY;
        return;
      }

      try {
        const loader = new GLTFLoader();
        const gltf = await loader.loadAsync(inst.definition.url);
        const obj = gltf.scene;
        obj.position.set(inst.offset.x, inst.offset.y, inst.offset.z);
        obj.rotation.y = inst.rotY;

        // Apply hubzz toon+outline to match in-world look (black cel-shade outline,
        // shaded toon ramp). See threeUtils.applyToonShader docstring — the returned
        // ShaderMaterial needs its outlineCameraPosition uniform updated every frame.
        const outlineMat = applyToonShader(obj, sharedGradientMap, camera.position);
        if (outlineMat) {
          outlineMatsRef.current.set(inst.definition.id, outlineMat);
        }

        scene.add(obj);
        loadedRef.current.set(inst.definition.id, obj);
      } catch (err) {
        console.error(`[PropLayer] failed to load ${inst.definition.url}`, err);
      }
    });
  }, [instances, scene]);

  // Cleanup all on unmount
  useEffect(() => {
    const map = loadedRef.current;
    const outlineMap = outlineMatsRef.current;
    const s = scene;
    return () => {
      for (const obj of map.values()) {
        s.remove(obj);
        obj.traverse((n) => {
          if ((n as THREE.Mesh).isMesh) {
            (n as THREE.Mesh).geometry?.dispose();
            const mat = (n as THREE.Mesh).material;
            if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
            else mat?.dispose();
          }
        });
      }
      for (const mat of outlineMap.values()) mat.dispose();
      map.clear();
      outlineMap.clear();
    };
  }, [scene]);

  return null;
}
