import React, { useEffect, useRef, useState } from 'react';
import * as Sentry from '@sentry/react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
import { obs } from '@/lib/obs';

/** Creates a gradient texture for MeshToonMaterial (discrete shading steps). */
function createToonGradientTexture(steps = 5) {
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

/** Replace mesh materials with MeshToonMaterial for toon shading. */
function applyToonShader(object3D, gradientMap) {
  object3D.traverse((node) => {
    if (!node.isMesh || !node.material) return;
    const orig = Array.isArray(node.material) ? node.material : [node.material];
    const toonMats = orig.map((m) => {
      const toon = new THREE.MeshToonMaterial({
        color: m.color?.clone?.() ?? new THREE.Color(0xffffff),
        map: m.map ?? null,
        normalMap: m.normalMap ?? null,
        normalScale: m.normalScale?.clone?.() ?? new THREE.Vector2(1, 1),
        alphaMap: m.alphaMap ?? null,
        transparent: m.transparent ?? false,
        depthWrite: m.depthWrite ?? true,
        side: m.side ?? THREE.FrontSide,
      });
      if (m.emissive) toon.emissive.copy(m.emissive);
      if (m.emissiveMap) toon.emissiveMap = m.emissiveMap;
      if (m.emissiveIntensity != null) toon.emissiveIntensity = m.emissiveIntensity;
      toon.gradientMap = gradientMap;
      return toon;
    });
    node.material = toonMats.length === 1 ? toonMats[0] : toonMats;
  });
}

const AltiiViewer = ({ vrmUrl }: { vrmUrl: string }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [hasWebGLError, setHasWebGLError] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [showHint, setShowHint] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setShowHint(false), 4000);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    setLoadError(false);
    if (!canvasRef.current || hasWebGLError || loadError) return;

    // Scene setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30.0, canvasRef.current.clientWidth / canvasRef.current.clientHeight, 0.1, 20.0);
    camera.position.set(0.0, 0.0, 5.0);

    let renderer: THREE.WebGLRenderer;
    try {
      const canvas = canvasRef.current;
      const glOptions = { failIfMajorPerformanceCascade: false, powerPreference: 'low-power' };
      const gl = canvas.getContext('webgl2', glOptions)
        ?? canvas.getContext('webgl', glOptions);
      if (!gl) throw new Error('Could not create WebGL context');
      renderer = new THREE.WebGLRenderer({ canvas, context: gl, antialias: true, alpha: true });
    } catch (error) {
      console.error('WebGL context creation failed:', error);
      Sentry.captureException(error, { tags: { kind: 'webgl.init' } });
      obs.exception('webgl.init', error);
      setHasWebGLError(true);
      return;
    }
    renderer.setSize(canvasRef.current.clientWidth, canvasRef.current.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x0d0d0d, 1);

    // Orbit controls — drag to rotate, scroll to zoom
    const controls = new OrbitControls(camera, canvasRef.current);
    controls.enablePan = false;
    controls.minDistance = 1;
    controls.maxDistance = 12;
    let userInteracting = false;
    controls.addEventListener('start', () => {
      userInteracting = true;
      setShowHint(false);
    });
    controls.addEventListener('end', () => { userInteracting = false; });

    // 3-point lighting for avatar visibility
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambient);
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.8);
    keyLight.position.set(2, 3, 4).normalize();
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xaabbff, 0.3);
    fillLight.position.set(-2, 1, 2).normalize();
    scene.add(fillLight);
    const rimLight = new THREE.DirectionalLight(0xffffcc, 0.2);
    rimLight.position.set(0, -1, -2).normalize();
    scene.add(rimLight);

    // Loader
    const loader = new GLTFLoader();
    loader.register((parser) => {
      return new VRMLoaderPlugin(parser);
    });

    let currentVrm = null;
    let currentScene = null;

    if (vrmUrl) {
      setLoading(true);
      setLoadError(false);
      loader.load(
        vrmUrl,
        (gltf) => {
          setLoading(false);
          const root = gltf.userData.vrm ? gltf.userData.vrm.scene : gltf.scene;
          const gradientMap = createToonGradientTexture(5);
          applyToonShader(root, gradientMap);
          if (gltf.userData.vrm) {
            const vrm = gltf.userData.vrm;
            scene.add(vrm.scene);
            currentVrm = vrm;
            currentScene = vrm.scene;
          } else {
            scene.add(gltf.scene);
            currentScene = gltf.scene;
          }

          // Center camera and orbit target
          if (currentScene) {
            const box = new THREE.Box3().setFromObject(currentScene);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            const fov = camera.fov * (Math.PI / 180);
            let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
            cameraZ *= 2.0;
            camera.position.set(0, center.y, cameraZ);
            controls.target.copy(center);
          }
        },
        (progressEvent) => {
           const p = (progressEvent.loaded / (progressEvent.total || 1000000)) * 100;
           setProgress(Math.round(p));
        },
        (error) => {
          setLoading(false);
          setLoadError(true);
          console.error('Error loading model:', error);
          Sentry.captureException(error, { tags: { kind: 'vrm.load' } });
          obs.exception('vrm.load', error);
        }
      );
    }

    // Animation loop
    const clock = new THREE.Clock();
    let animationId;
    const animate = () => {
      animationId = requestAnimationFrame(animate);

      const delta = clock.getDelta();
      if (currentVrm) {
        currentVrm.update(delta);
      }

      if (currentScene && !userInteracting) {
        currentScene.rotation.y += delta * 0.4;
      }

      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!canvasRef.current) return;
      camera.aspect = canvasRef.current.clientWidth / canvasRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(canvasRef.current.clientWidth, canvasRef.current.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationId);
      controls.dispose();
      renderer.dispose();
      scene.clear();
    };
  }, [vrmUrl, hasWebGLError, loadError]);

  if (hasWebGLError) {
    return (
      <div className="w-full h-full min-h-[200px] flex items-center justify-center bg-muted/30 border border-border rounded-lg">
        <div className="text-center p-6">
          <div className="text-primary font-bold mb-2 text-sm">3D PREVIEW UNAVAILABLE</div>
          <p className="text-muted-foreground text-xs">WebGL is disabled or not supported.</p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="w-full h-full min-h-[200px] flex flex-col items-center justify-center bg-muted/30 border border-border rounded-lg gap-2">
        <p className="text-sm text-muted-foreground">Model failed to load</p>
        <p className="text-xs text-muted-foreground">Check console or try another avatar</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative bg-[#0d0d0d] rounded-lg overflow-hidden cursor-grab active:cursor-grabbing">
      <canvas ref={canvasRef} className="block w-full h-full pointer-events-auto" />

      {showHint && !loading && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-full bg-black/60 text-white/90 text-xs animate-in fade-in duration-300">
          Drag to rotate · Scroll to zoom
        </div>
      )}

      {loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-background/80">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-muted-foreground">{progress}%</span>
        </div>
      )}

      {!vrmUrl && !loading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm text-muted-foreground">Awaiting 3D Model</span>
        </div>
      )}
    </div>
  );
};

export default AltiiViewer;
