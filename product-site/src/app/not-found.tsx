import Link from 'next/link';
import { BentoPanel, ProductShell } from '@/components/product-shell';

export default function NotFound() {
  return <ProductShell section="404 / NOT FOUND"><div className="bentoGrid singleGrid"><BentoPanel className="heroCell" label="ENTITY LOOKUP"><h1>NOT IN THE INDEX.</h1><p>The requested product identity does not exist in the current adapter.</p><Link className="systemButton primary" href="/explore/avatar-sets">RETURN TO SETS →</Link></BentoPanel></div></ProductShell>;
}
