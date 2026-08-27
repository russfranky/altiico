import Link from 'next/link';
import { SystemLabel } from '@altiico/ui';

export default function AvatarSetNotFound() {
  return <main className="setDetailState"><SystemLabel tone="signal">SET / NOT FOUND</SystemLabel><h1>Avatar set not found.</h1><p>The current catalog source did not return this product route.</p><Link href="/explore/avatar-sets">Return to the lineup →</Link></main>;
}
