import React, { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import * as Sentry from '@sentry/react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Environment, ContactShadows } from '@react-three/drei';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils, type VRM } from '@pixiv/three-vrm';
import { obs } from '@/lib/obs';

/* ─────────────────────────────────────────────
   Types
   ───────────────────────────────────────────── */

interface VRMViewerProps {
  /** URL to a .vrm file */
  url: string;
  /** Background color of the canvas (CSS value). Default: transparent over gradient */
  backgroundColor?: string;
  /** Disable the idle breathing / blink animation */
  disableIdleAnimation?: boolean;
  /** Initial camera distance multiplier (default 1.0) */
  cameraDistanceMultiplier?: number;
  /** Additional className on the root wrapper */
  className?: string;
}

/* ─────────────────────────────────────────────
   Idle animation helpers
   ───────────────────────────────────────────── */

/** Attempt to find a blend shape by common names */
function findExpression(vrm: VRM, candidates: string[]): string | null {
  const mgr = vrm.expressionManager;
  if (!mgr) return null;
  for (const name of candidates) {
    // expressionMap may not exist on all versions; fall back to getValue
    try {
      const val = mgr.getValue(name);
      if (val !== null && val !== undefined) return name;
    } catch {
      // expression not found, try next
    }
  }
  return null;
}

/* ─────────────────────────────────────────────
   VRM Scene (inner R3F component)
   ───────────────────────────────────────────── */

interface VRMSceneProps {
  url: string;
  onLoaded: () => void;
  onProgress: (pct: number) => void;
  onError: (msg: string) => void;
  disableIdleAnimation: boolean;
  cameraDistanceMultiplier: number;
}

function VRMScene({
  url,
  onLoaded,
  onProgress,
  onError,
  disableIdleAnimation,
  cameraDistanceMultiplier,
}: VRMSceneProps) {
  const { camera, scene } = useThree();
  const vrmRef = useRef<VRM | null>(null);
  const clockRef = useRef(new THREE.Clock());
  const blinkNameRef = useRef<string | null>(null);
  const autoRotateRef = useRef(0);

  // Load VRM
  useEffect(() => {
    let cancelled = false;
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      url,
      (gltf) => {
        if (cancelled) return;

        const vrm = gltf.userData.vrm as VRM | undefined;
        if (!vrm) {
          onError('File loaded but contains no VRM data.');
          return;
        }

        // Optimise — both utils throw on VRMs with InterleavedBufferAttribute
        // (common in meshopt-compressed GLBs). The optimisations are a
        // nice-to-have, not load-bearing: skip them for files that don't support
        // them rather than failing the whole load.
        try {
          VRMUtils.removeUnnecessaryVertices(gltf.scene);
          VRMUtils.removeUnnecessaryJoints(gltf.scene);
        } catch (e) {
          console.warn('[VRMViewer] skipping optimise pass:', e instanceof Error ? e.message : e);
          Sentry.addBreadcrumb({
            category: 'vrm.optimise',
            level: 'warning',
            message: 'skipping optimise pass',
            data: { err: e instanceof Error ? e.message : String(e) },
          });
          obs.warn('vrm.optimise', 'skipping optimise pass', {}, { err: e instanceof Error ? e.message : String(e) });
        }

        // Rotate if needed (VRM 0.x faces +Z). No-op for VRM 1.0 per spec.
        if (vrm.meta?.metaVersion === '0') {
          VRMUtils.rotateVRM0(vrm);
        }

        // Add to scene
        scene.add(vrm.scene);
        vrmRef.current = vrm;

        // Find blink expression
        blinkNameRef.current = findExpression(vrm, ['blink', 'Blink', 'blinkLeft']);

        // Frame camera on model
        const box = new THREE.Box3().setFromObject(vrm.scene);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = (camera as THREE.PerspectiveCamera).fov * (Math.PI / 180);
        const dist = Math.abs(maxDim / 2 / Math.tan(fov / 2)) * 1.8 * cameraDistanceMultiplier;

        camera.position.set(0, center.y, dist);
        (camera as THREE.PerspectiveCamera).lookAt(center);

        clockRef.current.start();
        onLoaded();
      },
      (evt) => {
        if (cancelled) return;
        const total = evt.total || evt.loaded * 2;
        onProgress(Math.min(99, Math.round((evt.loaded / total) * 100)));
      },
      (err) => {
        if (cancelled) return;
        console.error('[VRMViewer] Load error:', err);
        Sentry.captureException(err, { tags: { kind: 'vrm.load' } });
        obs.exception('vrm.load', err);
        onError(err instanceof Error ? err.message : 'Failed to load VRM file.');
      },
    );

    return () => {
      cancelled = true;
      if (vrmRef.current) {
        VRMUtils.deepDispose(vrmRef.current.scene);
        scene.remove(vrmRef.current.scene);
        vrmRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  // Per-frame update: idle animation + slow auto-rotate
  useFrame((_state, delta) => {
    const vrm = vrmRef.current;
    if (!vrm) return;

    vrm.update(delta);

    // Slow turntable rotation
    autoRotateRef.current += delta * 0.15;
    vrm.scene.rotation.y = autoRotateRef.current;

    if (disableIdleAnimation) return;

    const t = clockRef.current.getElapsedTime();
    const mgr = vrm.expressionManager;

    // Breathing: subtle body scale oscillation
    const breathScale = 1 + Math.sin(t * 1.2) * 0.003;
    vrm.scene.scale.setScalar(breathScale);

    // Blink every ~4 seconds
    if (mgr && blinkNameRef.current) {
      const blinkCycle = t % 4.0;
      let blinkVal = 0;
      if (blinkCycle > 3.6 && blinkCycle < 3.8) {
        // close
        blinkVal = Math.sin(((blinkCycle - 3.6) / 0.2) * Math.PI);
      }
      mgr.setValue(blinkNameRef.current, blinkVal);
    }
  });

  return null;
}

/* ─────────────────────────────────────────────
   Loading Spinner
   ───────────────────────────────────────────── */

function LoadingOverlay({ progress }: { progress: number }) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-4 pointer-events-none">
      {/* Animated ring */}
      <div className="relative w-16 h-16">
        <svg className="w-full h-full animate-spin" viewBox="0 0 64 64">
          <circle
            cx="32"
            cy="32"
            r="28"
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="3"
          />
          <circle
            cx="32"
            cy="32"
            r="28"
            fill="none"
            stroke="url(#spinner-grad)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${progress * 1.76} 176`}
            style={{ transition: 'stroke-dasharray 0.3s ease' }}
          />
          <defs>
            <linearGradient id="spinner-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#a78bfa" />
              <stop offset="100%" stopColor="#6366f1" />
            </linearGradient>
          </defs>
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-xs font-semibold text-white/80 tabular-nums">
          {progress}%
        </span>
      </div>
      <span className="text-xs text-white/50 tracking-wide uppercase">Loading avatar</span>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Error display
   ───────────────────────────────────────────── */

function ErrorOverlay({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-black/60 backdrop-blur-sm">
      <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      </div>
      <p className="text-sm text-white/70 max-w-[260px] text-center leading-relaxed">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 px-4 py-1.5 rounded-full text-xs font-medium bg-white/10 text-white/80 hover:bg-white/20 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────
   Controls hint (fades out)
   ───────────────────────────────────────────── */

function ControlsHint({ visible }: { visible: boolean }) {
  return (
    <div
      className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 pointer-events-none transition-opacity duration-700"
      style={{ opacity: visible ? 1 : 0 }}
    >
      <div className="flex items-center gap-3 px-4 py-2 rounded-full bg-black/50 backdrop-blur-md border border-white/[0.06]">
        <span className="text-[11px] text-white/50 tracking-wide">
          Drag to orbit
        </span>
        <span className="w-px h-3 bg-white/10" />
        <span className="text-[11px] text-white/50 tracking-wide">
          Scroll to zoom
        </span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Main exported component
   ───────────────────────────────────────────── */

const VRMViewer: React.FC<VRMViewerProps> = ({
  url,
  backgroundColor,
  disableIdleAnimation = false,
  cameraDistanceMultiplier = 1.0,
  className = '',
}) => {
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  const handleLoaded = useCallback(() => {
    setLoading(false);
    setProgress(100);
    setShowHint(true);
    // Hide hint after 4 seconds
    setTimeout(() => setShowHint(false), 4000);
  }, []);

  const handleProgress = useCallback((pct: number) => {
    setProgress(pct);
  }, []);

  const handleError = useCallback((msg: string) => {
    setLoading(false);
    setError(msg);
  }, []);

  const handleRetry = useCallback(() => {
    setLoading(true);
    setProgress(0);
    setError(null);
    setRetryKey((k) => k + 1);
  }, []);

  // Reset state when URL changes
  useEffect(() => {
    setLoading(true);
    setProgress(0);
    setError(null);
  }, [url]);

  // Memoize orbit target so it doesn't recreate each render
  const orbitTarget = useMemo(() => new THREE.Vector3(0, 0.85, 0), []);

  return (
    <div
      className={`relative w-full h-full min-h-[300px] overflow-hidden rounded-xl select-none ${className}`}
      style={{
        background: backgroundColor ?? 'linear-gradient(145deg, #0c0c14 0%, #121220 40%, #0e0e1a 100%)',
        cursor: 'grab',
      }}
    >
      {/* Subtle vignette overlay */}
      <div
        className="absolute inset-0 z-[1] pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.5) 100%)',
        }}
      />

      {/* Three.js Canvas */}
      <Canvas
        key={retryKey}
        className="!absolute inset-0 z-[2]"
        camera={{ fov: 30, near: 0.1, far: 100, position: [0, 1, 5] }}
        dpr={[1, 2]}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.1,
        }}
        onCreated={({ gl }) => {
          gl.outputColorSpace = THREE.SRGBColorSpace;
        }}
      >
        {/* Lighting rig -- soft, cinematic look */}
        <ambientLight intensity={0.5} color="#e8e0ff" />
        <directionalLight
          position={[3, 5, 4]}
          intensity={1.0}
          color="#ffffff"
          castShadow={false}
        />
        <directionalLight
          position={[-3, 2, 2]}
          intensity={0.4}
          color="#b0b8ff"
        />
        {/* Rim / back light for edge separation */}
        <directionalLight
          position={[0, 3, -4]}
          intensity={0.3}
          color="#ffe4c9"
        />
        {/* Subtle bottom fill to reduce harsh under-chin shadows */}
        <directionalLight
          position={[0, -2, 2]}
          intensity={0.15}
          color="#8888aa"
        />

        {/* Soft contact shadow on the ground plane */}
        <ContactShadows
          position={[0, -0.01, 0]}
          opacity={0.35}
          scale={8}
          blur={2.5}
          far={3}
          color="#1a1a2e"
        />

        {/* Orbit controls */}
        <OrbitControls
          makeDefault
          enablePan={false}
          minDistance={1.2}
          maxDistance={10}
          minPolarAngle={Math.PI * 0.15}
          maxPolarAngle={Math.PI * 0.75}
          target={orbitTarget}
          enableDamping
          dampingFactor={0.08}
          rotateSpeed={0.5}
          zoomSpeed={0.7}
        />

        {/* The VRM model */}
        {!error && (
          <VRMScene
            url={url}
            onLoaded={handleLoaded}
            onProgress={handleProgress}
            onError={handleError}
            disableIdleAnimation={disableIdleAnimation}
            cameraDistanceMultiplier={cameraDistanceMultiplier}
          />
        )}
      </Canvas>

      {/* UI overlays */}
      {loading && <LoadingOverlay progress={progress} />}
      {error && <ErrorOverlay message={error} onRetry={handleRetry} />}
      {!loading && !error && <ControlsHint visible={showHint} />}
    </div>
  );
};

export default VRMViewer;
