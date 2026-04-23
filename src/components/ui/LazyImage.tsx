import { useState, useRef, useEffect, type ImgHTMLAttributes } from 'react';
import { PLACEHOLDER_IMG } from '@/data/altiiData';

interface LazyImageProps extends ImgHTMLAttributes<HTMLImageElement> {
  /** Fallback src on error (defaults to PLACEHOLDER_IMG) */
  fallbackSrc?: string;
}

/**
 * Image component with:
 * - Native loading="lazy" for below-the-fold images
 * - IntersectionObserver for browsers with poor native lazy support
 * - Fade-in transition on load
 * - Error fallback to placeholder
 */
export default function LazyImage({
  src,
  alt = '',
  className = '',
  fallbackSrc = PLACEHOLDER_IMG,
  ...props
}: LazyImageProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // If IntersectionObserver is not available, just show immediately
    if (!('IntersectionObserver' in window)) {
      setInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin: '200px' } // Start loading 200px before viewport
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const handleError = () => {
    if (!error) {
      setError(true);
    }
  };

  return (
    <img
      ref={ref}
      src={inView ? (error ? fallbackSrc : src) : undefined}
      alt={alt}
      loading="lazy"
      decoding="async"
      onLoad={() => setLoaded(true)}
      onError={handleError}
      className={`${className} transition-opacity duration-300 ${loaded || !inView ? 'opacity-100' : 'opacity-0'}`}
      {...props}
    />
  );
}
