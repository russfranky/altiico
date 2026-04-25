import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import type { VRM } from '@pixiv/three-vrm';
import { loadMixamoAnimation } from '@/lib/mixamoLoader';
import { loadUALAnimation } from '@/lib/ualLoader';
import {
  HUBZZ_CAMERA_OFFSET,
  HUBZZ_ORTHO_HALF_HEIGHT,
  HUBZZ_TILE_SIZE,
  HUBZZ_SAFE_VOLUME_HEIGHT,
  AVATAR_TARGET_HEIGHT_MIN,
  AVATAR_TARGET_HEIGHT_MAX,
  HUBZZ_SEAT_HEIGHTS,
  computeOrthoFrustum,
} from '@/hooks/useHubzzCamera';
import type { SeatHeightStandard } from '@/hooks/useHubzzCamera';
import { PropLayer } from './PropLayer';
import { AvatarDragHandles } from './AvatarDragHandles';
import type { DragOffset } from './AvatarDragHandles';
import HubzzCameraControls from './HubzzCameraControls';
import type { HubzzCameraControlsHandle } from './HubzzCameraControls';
import type { PropInstance } from '@/lib/propsTypes';
import { applyToonShader, createToonGradientTexture } from '@/lib/threeUtils';
import AvatarLoadingFX from './AvatarLoadingFX';

// Shared gradient across every VRM load — identical toon ramp to hubzz default (5 steps)
const vrmGradientMap = createToonGradientTexture(5);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface IsometricCanvasProps {
  vrmUrl: string;
  fbxUrl?: string;
  /** Quaternius UAL clip spec — when set, takes precedence over fbxUrl. */
  ualClip?: { url: string; clipName: string };
  playing?: boolean;
  speed?: number;
  loop?: boolean;
  showBones?: boolean;
  showBounds?: boolean;
  seatHeight?: SeatHeightStandard;  // 'none' | 'floor' | 'chair' | 'stool'
  avatarFacingDeg?: number;         // 0 | 90 | 180 | 270 — hubzz sitTarget equivalent
  dragEnabled?: boolean;            // true = user can click-drag avatar to rig it
  onDragOffsetChange?: (offset: DragOffset) => void;
  onDragClampedChange?: (clamped: boolean) => void;
  props?: PropInstance[];
  onLoad?: (vrm: VRM) => void;
  onError?: (error: Error) => void;
}

export interface IsometricCanvasHandle {
  resetCamera: () => void;
  resetAvatarPosition: () => void;
}

// ---------------------------------------------------------------------------
// Inner scene (runs inside <Canvas>)
// ---------------------------------------------------------------------------

interface SceneProps {
  vrmUrl: string;
  fbxUrl?: string;
  ualClip?: { url: string; clipName: string };
  playing: boolean;
  speed: number;
  loop: boolean;
  showBones: boolean;
  showBounds: boolean;
  seatHeight: SeatHeightStandard;
  avatarFacingDeg: number;
  dragEnabled: boolean;
  onDragOffsetChange?: (offset: DragOffset) => void;
  onDragClampedChange?: (clamped: boolean) => void;
  onLoad?: (vrm: VRM) => void;
  onError?: (error: Error) => void;
  cameraControlsRef: React.RefObject<HubzzCameraControlsHandle | null>;
  onAvatarDragActive?: (active: boolean) => void;
}

function TileFloor() {
  return (
    <mesh
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, 0, 0]}
      receiveShadow
    >
      <planeGeometry args={[HUBZZ_TILE_SIZE, HUBZZ_TILE_SIZE]} />
      <meshBasicMaterial color="#1a1a2e" side={THREE.DoubleSide} />
    </mesh>
  );
}

function TileGrid() {
  // 1×1 wireframe tile at y=0 — renders on top of the floor plane to show tile edges
  const edges = React.useMemo(() => {
    const geo = new THREE.PlaneGeometry(HUBZZ_TILE_SIZE, HUBZZ_TILE_SIZE);
    return new THREE.EdgesGeometry(geo);
  }, []);

  return (
    <lineSegments
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, 0.001, 0]}
    >
      <primitive object={edges} attach="geometry" />
      <lineBasicMaterial color="#4444aa" linewidth={1} />
    </lineSegments>
  );
}

function BoundsBox() {
  // Two stacked 1×1×1 voxel boxes showing safe animation volume — renders the midline
  // at y=1 so it reads as "2 tiles tall" to match sandbox editor voxel stacks.
  // Avatars should be 1.5–1.75m tall. Arms/legs that escape this box will visibly
  // clip neighbors or tiles in-world.
  const edges = React.useMemo(() => {
    const geo = new THREE.BoxGeometry(HUBZZ_TILE_SIZE, HUBZZ_TILE_SIZE, HUBZZ_TILE_SIZE);
    return new THREE.EdgesGeometry(geo);
  }, []);

  // Target-height band: faint rings at 1.5m and 1.75m to visualize ideal avatar range
  const targetBand = React.useMemo(() => {
    const s = HUBZZ_TILE_SIZE / 2;
    const ring = (y: number) => {
      const pts = [
        new THREE.Vector3(-s, y, -s), new THREE.Vector3( s, y, -s),
        new THREE.Vector3( s, y, -s), new THREE.Vector3( s, y,  s),
        new THREE.Vector3( s, y,  s), new THREE.Vector3(-s, y,  s),
        new THREE.Vector3(-s, y,  s), new THREE.Vector3(-s, y, -s),
      ];
      return new THREE.BufferGeometry().setFromPoints(pts);
    };
    return { min: ring(AVATAR_TARGET_HEIGHT_MIN), max: ring(AVATAR_TARGET_HEIGHT_MAX) };
  }, []);

  return (
    <>
      {/* Lower voxel: 1×1×1 centered at y=0.5 */}
      <lineSegments position={[0, HUBZZ_TILE_SIZE / 2, 0]}>
        <primitive object={edges} attach="geometry" />
        <lineBasicMaterial color="#ff6644" linewidth={1} />
      </lineSegments>
      {/* Upper voxel: 1×1×1 centered at y=1.5 — shares midline edge with lower */}
      <lineSegments position={[0, HUBZZ_TILE_SIZE * 1.5, 0]}>
        <primitive object={edges} attach="geometry" />
        <lineBasicMaterial color="#ff6644" linewidth={1} />
      </lineSegments>
      {/* Ideal avatar height band: 1.5m (lower) and 1.75m (upper) */}
      <lineSegments>
        <primitive object={targetBand.min} attach="geometry" />
        <lineBasicMaterial color="#44ffaa" linewidth={1} transparent opacity={0.4} />
      </lineSegments>
      <lineSegments>
        <primitive object={targetBand.max} attach="geometry" />
        <lineBasicMaterial color="#44ffaa" linewidth={1} transparent opacity={0.4} />
      </lineSegments>
    </>
  );
}

function OrthoCamera() {
  const { camera, size, set } = useThree();

  // On mount: replace the default camera with an orthographic one
  useEffect(() => {
    const aspect = size.width / size.height;
    const frustum = computeOrthoFrustum(aspect);

    const ortho = new THREE.OrthographicCamera(
      frustum.left,
      frustum.right,
      frustum.top,
      frustum.bottom,
      frustum.near,
      frustum.far,
    );
    ortho.zoom = 2.0;
    ortho.position.copy(HUBZZ_CAMERA_OFFSET);
    ortho.lookAt(0, 0, 0);
    ortho.updateProjectionMatrix();

    set({ camera: ortho });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep frustum in sync with canvas resize
  useEffect(() => {
    if (!(camera instanceof THREE.OrthographicCamera)) return;
    const aspect = size.width / size.height;
    const frustum = computeOrthoFrustum(aspect);
    camera.left = frustum.left;
    camera.right = frustum.right;
    camera.top = frustum.top;
    camera.bottom = frustum.bottom;
    camera.updateProjectionMatrix();
  }, [camera, size]);

  return null;
}

function AvatarAndAnimation({
  vrmUrl,
  fbxUrl,
  ualClip,
  playing,
  speed,
  loop,
  showBones,
  showBounds,
  seatHeight,
  avatarFacingDeg,
  dragEnabled,
  onDragOffsetChange,
  onDragClampedChange,
  onLoad,
  onError,
  cameraControlsRef,
  onAvatarDragActive,
}: SceneProps) {
  const { scene: threeScene, camera } = useThree();
  const vrmRef = useRef<VRM | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const actionRef = useRef<THREE.AnimationAction | null>(null);
  const clockRef = useRef(new THREE.Clock());
  const mountedRef = useRef(true);
  const vrmOutlineMatRef = useRef<THREE.ShaderMaterial | null>(null);
  const loadingFxRef = useRef<AvatarLoadingFX | null>(null);

  // Whether avatar drag has captured the pointer (blocks camera pan)
  const [avatarDragActive, setAvatarDragActive] = useState(false);
  useEffect(() => {
    onAvatarDragActive?.(avatarDragActive);
  }, [avatarDragActive, onAvatarDragActive]);

  // Cleanup helpers
  const disposeAnimation = useCallback(() => {
    if (actionRef.current) {
      actionRef.current.stop();
      actionRef.current = null;
    }
    if (mixerRef.current) {
      mixerRef.current.stopAllAction();
      mixerRef.current = null;
    }
  }, []);

  const disposeVRM = useCallback(() => {
    disposeAnimation();
    if (vrmRef.current) {
      threeScene.remove(vrmRef.current.scene);
      VRMUtils.deepDispose(vrmRef.current.scene);
      vrmRef.current = null;
    }
    if (vrmOutlineMatRef.current) {
      vrmOutlineMatRef.current.dispose();
      vrmOutlineMatRef.current = null;
    }
  }, [threeScene, disposeAnimation]);

  // Helpers to add/remove the in-world-style loading FX during VRM streaming.
  const showLoadingFx = useCallback(() => {
    if (loadingFxRef.current) return;
    const fx = new AvatarLoadingFX(6);
    // Place at avatar chest height so it's framed the same way the arriving VRM will be.
    fx.position.set(0, 1.0, 0);
    threeScene.add(fx);
    loadingFxRef.current = fx;
  }, [threeScene]);

  const hideLoadingFx = useCallback(() => {
    const fx = loadingFxRef.current;
    if (!fx) return;
    threeScene.remove(fx);
    fx.dispose();
    loadingFxRef.current = null;
  }, [threeScene]);

  // Load VRM
  useEffect(() => {
    mountedRef.current = true;
    disposeVRM();
    hideLoadingFx();

    if (!vrmUrl) return;
    showLoadingFx();

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.loadAsync(vrmUrl)
      .then((gltf) => {
        if (!mountedRef.current) return;

        const vrm: VRM = gltf.userData.vrm;
        if (!vrm) {
          const err = new Error('GLTF loaded but no VRM data found');
          onError?.(err);
          hideLoadingFx();
          return;
        }

        // Face +Z (canonical hubzz orientation). Only VRM 0.x ships Z-forward;
        // VRM 1.0 is already Y-forward per spec, so rotateVRM0 + rotation.y=π
        // would double-flip it backward. Gate both on metaVersion.
        const isVRM0 = vrm.meta?.metaVersion === '0';
        if (isVRM0) {
          VRMUtils.rotateVRM0(vrm);
        }

        // Prevent avatar blinking when partially off-screen — intentional, matches hubzz
        vrm.scene.traverse((node) => {
          if ((node as THREE.SkinnedMesh).isSkinnedMesh) {
            node.frustumCulled = false;
          }
        });

        // Hubzz full scale chain — final size = VRM.scale × EntityAvatar.scale × worldEntityScale
        // (1) bounding-box normalization (EntityAvatar.adjustAvatarScale at EntityAvatar.ts:320-335)
        // (2) × 2.0 from EntityAvatar's own parent scale (EntityAvatar.ts:640)
        // (3) × worldEntityScale (default 1.0 — rooftop uses default, World.ts:149)
        // See NORTH_STAR.md "VRM scale normalization".
        const bbox = new THREE.Box3().setFromObject(vrm.scene);
        const bboxSize = new THREE.Vector3();
        bbox.getSize(bboxSize);
        const scaleVec = new THREE.Vector3(0.7, 0.7, 0.7).divide(bboxSize);
        const normalizedScale = Math.min(scaleVec.x, Math.min(scaleVec.y, scaleVec.z)) * 1.8;
        const ENTITY_AVATAR_SCALE = 2.0;
        vrm.scene.scale.setScalar(normalizedScale * ENTITY_AVATAR_SCALE);

        // Face camera — hubzz applies rotation.y = π for non-bot VRM 0.x avatars
        // (EntityAvatar.ts:331). VRM 1.0 is already -Z-facing per spec.
        // Base rotation set here; avatarFacingDeg effect below layers on top for sitTarget testing.
        if (isVRM0) {
          vrm.scene.rotation.y = Math.PI;
        }

        // Initial position — seat height offset applied reactively in a separate effect below
        vrm.scene.position.set(0, 0, 0);

        // Apply hubzz toon+outline shader to the VRM — matches in-world rendering.
        // Returned ShaderMaterial has an outlineCameraPosition uniform that must be
        // updated every frame in the useFrame hook below.
        const outlineMat = applyToonShader(vrm.scene, vrmGradientMap, camera.position);
        vrmOutlineMatRef.current = outlineMat;

        threeScene.add(vrm.scene);
        vrmRef.current = vrm;
        clockRef.current = new THREE.Clock();

        hideLoadingFx();
        onLoad?.(vrm);
      })
      .catch((err: Error) => {
        if (!mountedRef.current) return;
        hideLoadingFx();
        onError?.(err);
      });

    return () => {
      mountedRef.current = false;
      disposeVRM();
      hideLoadingFx();
    };
  // Intentionally omitting disposeVRM — stable ref
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vrmUrl]);

  // Reactive facing rotation — equivalent to hubzz sitTarget.lookAt.
  // `avatarFacingDeg` layers on top of the base π rotation so 0° = camera-facing
  // (hubzz default), 90° = avatar's right, 180° = away from camera, 270° = avatar's left.
  useEffect(() => {
    const vrm = vrmRef.current;
    if (!vrm) return;
    vrm.scene.rotation.y = Math.PI + (avatarFacingDeg * Math.PI) / 180;
  }, [avatarFacingDeg, vrmUrl]);

  // Exact port of hubzz `EntityAvatar.snapToTilePosition` (EntityAvatar.ts:793-811).
  // Triggered once, after an animation's setAction() completes — same as hubzz
  // at AvatarAnimationManager.ts:260-262. NOT per-frame. NOT on seat change alone.
  //
  // Algorithm (from hubzz source — do not deviate):
  //   position.copy(tile.position)               // tile position = (0, 0, 0) in altiico
  //   if (tile.sittable):
  //     if (pelvisBone):
  //       updateWorldMatrix(true, true)
  //       pelvisWorld = pelvisBone.getWorldPosition()
  //       delta = position - pelvisWorld
  //       position += delta * 0.5
  //       position.y += 0.3
  //     else:
  //       position.y -= (anim starts with 'anim_sit') ? (hipHeight / 3) : 0
  const snapTriggerRef = useRef(0);
  useEffect(() => {
    const vrm = vrmRef.current;
    if (!vrm) return;

    // Defer to next microtask so the action.play() call inside the animation
    // load effect has run first. Same ordering as hubzz where snapToTilePosition
    // is called at the tail of setAction() after action.play().
    const trigger = ++snapTriggerRef.current;

    requestAnimationFrame(() => {
      if (trigger !== snapTriggerRef.current) return;
      const scene = vrm.scene;

      // Hubzz: this.position.copy(this.tile.position). In altiico, tile is origin.
      scene.position.set(0, 0, 0);

      if (seatHeight === 'none') {
        // Not on a sittable tile — nothing more to do
        return;
      }

      const pelvisBone = scene.getObjectByName('Hips') as THREE.Bone | null;

      if (pelvisBone) {
        // Hubzz: updateWorldMatrix(true, true); then pelvisBone.getWorldPosition
        scene.updateWorldMatrix(true, true);
        const pelvisWorld = new THREE.Vector3();
        pelvisBone.getWorldPosition(pelvisWorld);

        // Hubzz: const delta = new Vector3().subVectors(this.position, pelvisWorld)
        const delta = new THREE.Vector3().subVectors(scene.position, pelvisWorld);

        // Hubzz: this.position.add(delta.multiplyScalar(0.5)); this.position.y += 0.3
        scene.position.add(delta.multiplyScalar(0.5));
        scene.position.y += 0.3;
      } else {
        // Fallback — hubzz: this.position.y -= anim.startsWith('anim_sit') ? (hipHeight / 3) : 0
        const isSitAnim = !!fbxUrl && (fbxUrl.includes('anim_sit') || fbxUrl.includes('/sit'));
        if (isSitAnim) {
          // Approximate hipHeight from bbox (hubzz measures it from animation clips,
          // altiico doesn't track it). Using 40% of bbox height as rough proxy.
          const bbox = new THREE.Box3().setFromObject(scene);
          const size = new THREE.Vector3();
          bbox.getSize(size);
          const approxHipHeight = size.y * 0.4;
          scene.position.y -= approxHipHeight / 3;
        }
      }
    });
  }, [seatHeight, vrmUrl, fbxUrl]);

  // Load animation when fbxUrl/ualClip or vrm changes. UAL takes precedence.
  useEffect(() => {
    disposeAnimation();

    const vrm = vrmRef.current;
    if (!vrm) return;
    if (!ualClip && !fbxUrl) return;

    let cancelled = false;

    const loader = ualClip
      ? loadUALAnimation(ualClip.url, ualClip.clipName, vrm)
      : (loadMixamoAnimation(fbxUrl!, vrm) as Promise<{ clip: THREE.AnimationClip } | null>);

    loader
      .then((result: any) => {
        if (cancelled || !vrmRef.current || !result?.clip) return;

        const mixer = new THREE.AnimationMixer(vrmRef.current.scene);
        const action = mixer.clipAction(result.clip);
        action.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
        action.clampWhenFinished = !loop;
        action.timeScale = speed;
        if (playing) action.play();

        mixerRef.current = mixer;
        actionRef.current = action;
      })
      .catch((err: Error) => {
        if (cancelled) return;
        onError?.(err);
      });

    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fbxUrl, ualClip?.url, ualClip?.clipName, vrmRef.current]);

  // Sync playing / speed / loop without reloading
  useEffect(() => {
    const action = actionRef.current;
    if (!action) return;

    action.timeScale = speed;
    action.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);

    if (playing) {
      action.paused = false;
      if (!action.isRunning()) action.play();
    } else {
      action.paused = true;
    }
  }, [playing, speed, loop]);

  // Advance VRM + mixer each frame
  useFrame(() => {
    const delta = clockRef.current.getDelta();
    if (vrmRef.current) {
      vrmRef.current.update(delta);
    }
    if (mixerRef.current) {
      mixerRef.current.update(delta);
    }
    if (loadingFxRef.current) {
      loadingFxRef.current.update();
    }
    // Keep the VRM outline uniform aligned with the camera so angle-based thickness
    // stays correct. See applyToonShader() docstring.
    if (vrmOutlineMatRef.current) {
      vrmOutlineMatRef.current.uniforms.outlineCameraPosition.value.copy(camera.position);
    }
  });

  return (
    <>
      {showBones && vrmRef.current && (
        <primitive object={new THREE.SkeletonHelper(vrmRef.current.scene)} />
      )}
      {showBounds && <BoundsBox />}
      {/* Seat surface indicator only renders when seat > 'none'. It visualizes
          the target height where a sittable PROP'S seat surface should land. */}
      {seatHeight !== 'none' && (
        <SeatSurfaceIndicator height={HUBZZ_SEAT_HEIGHTS[seatHeight]} />
      )}
      <AvatarDragHandles
        target={vrmRef.current?.scene ?? null}
        enabled={dragEnabled}
        onOffsetChange={(offset) => onDragOffsetChange?.(offset)}
        onClampedChange={onDragClampedChange}
      />
    </>
  );
}

function SeatSurfaceIndicator({ height }: { height: number }) {
  // Translucent yellow plane at the active seat height, plus a ring at tile-edge.
  // Gives a visible target for where the avatar's feet should land when sitting.
  return (
    <group position={[0, height, 0]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[HUBZZ_TILE_SIZE, HUBZZ_TILE_SIZE]} />
        <meshBasicMaterial color="#ffcc44" transparent opacity={0.35} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 10, 5]} intensity={0.8} />
      <directionalLight position={[-3, 5, -3]} intensity={0.3} color="#aabbff" />
    </>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

const IsometricCanvas = forwardRef<IsometricCanvasHandle, IsometricCanvasProps>(
  function IsometricCanvas(
    {
      vrmUrl,
      fbxUrl,
      ualClip,
      playing = true,
      speed = 1.0,
      loop = true,
      showBones = false,
      showBounds = false,
      seatHeight = 'none',
      avatarFacingDeg = 0,
      dragEnabled = false,
      onDragOffsetChange,
      onDragClampedChange,
      props: propInstances = [],
      onLoad,
      onError,
    },
    ref,
  ) {
    const cameraControlsRef = useRef<HubzzCameraControlsHandle | null>(null);
    const [avatarDragActive, setAvatarDragActive] = useState(false);

    useImperativeHandle(ref, () => ({
      resetCamera() {
        cameraControlsRef.current?.resetCamera();
      },
      resetAvatarPosition() {
        // Clearing the avatar offset is handled by AvatarDragHandles' target-change effect.
        // This method is available for external imperative reset if needed.
      },
    }));

    return (
      <div style={{ width: '100%', height: '100%', position: 'relative' }}>
        <Canvas
          orthographic
          camera={{
            position: [HUBZZ_CAMERA_OFFSET.x, HUBZZ_CAMERA_OFFSET.y, HUBZZ_CAMERA_OFFSET.z],
            zoom: 2,
            near: 0.1,
            far: 1000,
          }}
          gl={{ antialias: true, alpha: false, preserveDrawingBuffer: true }}
          style={{ background: '#0d0d1a' }}
        >
          {/* Override the auto-created camera with our canonical ortho camera */}
          <OrthoCamera />

          <Lights />

          <TileFloor />
          <TileGrid />
          <PropLayer instances={propInstances} />

          <AvatarAndAnimation
            vrmUrl={vrmUrl}
            fbxUrl={fbxUrl}
            ualClip={ualClip}
            playing={playing}
            speed={speed}
            loop={loop}
            showBones={showBones}
            showBounds={showBounds}
            seatHeight={seatHeight}
            avatarFacingDeg={avatarFacingDeg}
            dragEnabled={dragEnabled}
            onDragOffsetChange={onDragOffsetChange}
            onDragClampedChange={onDragClampedChange}
            onLoad={onLoad}
            onError={onError}
            cameraControlsRef={cameraControlsRef}
            onAvatarDragActive={setAvatarDragActive}
          />

          {/* HubzzCameraControls replaces OrbitControls — scroll-zoom + click-drag-to-pan,
              no rotation ever. panBlocked=true when avatar drag has captured the pointer. */}
          <HubzzCameraControls
            ref={cameraControlsRef}
            panBlocked={avatarDragActive}
          />
        </Canvas>
      </div>
    );
  },
);

export default IsometricCanvas;
