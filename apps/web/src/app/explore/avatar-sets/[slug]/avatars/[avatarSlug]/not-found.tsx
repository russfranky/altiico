import Link from 'next/link';
import { SystemLabel } from '@altiico/ui';

export default function AvatarDetailNotFound() {
  return <main className="avatarDetailState"><SystemLabel tone="signal">ENTITY / NOT FOUND</SystemLabel><h1>Avatar record not found.</h1><p>The product route did not resolve to a known avatar record.</p><Link href="/explore/avatar-sets">Return to avatar sets →</Link></main>;
}
