import { SystemLabel } from '@altiico/ui';
import type { AvatarProductIdentity } from '../../domain';
import { displayOptional } from '../../presentation/format';

export function AvatarIdentityPanel({ identity }: { identity: AvatarProductIdentity }) {
  return (
    <div className="avatarDetailPanel">
      <SystemLabel tone="signal">IDENTITY / SEPARATE KEYS</SystemLabel>
      <h2>THE PAGE ID IS NOT THE TOKEN ID.</h2>
      <p>Product, route, source, API, and on-chain identity stay separate so adapters can reconcile them without loss.</p>
      <dl className="avatarIdentityReadout">
        <div><dt>PRODUCT AVATAR ID</dt><dd>{identity.productAvatarId}</dd></div>
        <div><dt>ROUTE SLUG</dt><dd>{identity.avatarSlug}</dd></div>
        <div><dt>PRODUCT SET ID</dt><dd>{identity.productSetId}</dd></div>
        <div><dt>SOURCE ASSET ID</dt><dd>{displayOptional(identity.sourceAssetId)}</dd></div>
        <div><dt>API AVATAR ID</dt><dd>{displayOptional(identity.apiAvatarId)}</dd></div>
        <div><dt>TOKEN ID</dt><dd>{displayOptional(identity.tokenId)}</dd></div>
        <div><dt>CHAIN</dt><dd>{displayOptional(identity.chain)}</dd></div>
        <div><dt>CONTRACT</dt><dd className="avatarLongValue">{displayOptional(identity.contractAddress)}</dd></div>
      </dl>
    </div>
  );
}
