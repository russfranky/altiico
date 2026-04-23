import { useState, useEffect, type RefObject } from 'react';
import type { WebGLRenderer } from 'three';

interface UseWebGLRendererResult {
  renderer: WebGLRenderer | null;
  hasWebGLError: boolean;
  errorMessage: string | null;
}

/**
 * Custom hook to create a WebGLRenderer with robust error handling and fallback context creation.
 * Dynamically imports three.js so it is NOT pulled into the initial bundle.
 * @param canvasRef Reference to the canvas element
 * @returns Object containing the renderer instance and error state
 */
export function useWebGLRenderer(canvasRef: RefObject<HTMLCanvasElement | null>): UseWebGLRendererResult {
  const [renderer, setRenderer] = useState<WebGLRenderer | null>(null);
  const [hasWebGLError, setHasWebGLError] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    let newRenderer: WebGLRenderer | null = null;
    let disposed = false;

    // Dynamically import three.js so the ~560KB chunk is only fetched
    // when a component actually needs WebGL rendering.
    import('three').then((THREE) => {
      if (disposed || !canvasRef.current) return;

      try {
        const canvas = canvasRef.current;
        const glOptions = { failIfMajorPerformanceCaveat: true, powerPreference: 'low-power' as const };

        const gl = canvas.getContext('webgl2', glOptions)
          ?? canvas.getContext('webgl', glOptions);

        if (!gl) {
          throw new Error('WebGL is not available. Please ensure "Use graphics acceleration" is enabled in your browser settings.');
        }

        newRenderer = new THREE.WebGLRenderer({
          canvas,
          context: gl as WebGLRenderingContext,
          antialias: true,
          alpha: true,
        });

        newRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        setRenderer(newRenderer);
        setHasWebGLError(false);
        setErrorMessage(null);
      } catch (error) {
        console.error("WebGL context creation failed:", error);
        setHasWebGLError(true);
        setErrorMessage(error instanceof Error ? error.message : "WebGL context creation failed");

        if (newRenderer) {
          newRenderer.dispose();
          newRenderer = null;
        }
      }
    }).catch((error) => {
      if (!disposed) {
        console.error("Failed to load three.js:", error);
        setHasWebGLError(true);
        setErrorMessage("Failed to load 3D engine");
      }
    });

    return () => {
      disposed = true;
      if (newRenderer) {
        newRenderer.dispose();
      }
      setRenderer(null);
    };
  }, [canvasRef]);

  return { renderer, hasWebGLError, errorMessage };
}
