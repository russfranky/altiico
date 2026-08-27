'use client';
import { SystemButton, SystemLabel } from '@altiico/ui';
export default function CatalogError({ reset }: { error: Error; reset: () => void }) {
  return <main className="catalogState"><SystemLabel tone="signal">CATALOG / ERROR</SystemLabel><h1>THE LINEUP IS OFFLINE.</h1><p>The current catalog source failed. No fallback result was substituted.</p><button onClick={reset}>TRY AGAIN</button><SystemButton variant="secondary" href="/">RETURN HOME</SystemButton></main>;
}
