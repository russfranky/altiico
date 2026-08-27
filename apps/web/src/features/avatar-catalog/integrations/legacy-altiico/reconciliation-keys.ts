import type { CatalogReconciliationKey } from '../../domain';
import type { LegacyAltiicoSourceAvatar, LegacyAltiicoStagingSet } from './contracts';
import { normalizeChain, normalizeContract } from './identifiers';

export function buildLegacySetReconciliationKeys(item: LegacyAltiicoStagingSet): CatalogReconciliationKey[] {
  const keys: CatalogReconciliationKey[] = [];
  if (item.set.chain && item.set.contract) {
    keys.push({
      kind: 'chain-contract',
      value: `${normalizeChain(item.set.chain)}:${normalizeContract(item.set.contract)}`,
      priority: 1,
    });
  }
  keys.push({ kind: 'source-collection', value: `legacy-altiico:${item.set.slug}`, priority: 2 });
  return keys;
}

export function buildLegacyAvatarReconciliationKeys(
  set: LegacyAltiicoStagingSet,
  avatar: LegacyAltiicoSourceAvatar,
): CatalogReconciliationKey[] {
  const keys: CatalogReconciliationKey[] = [];
  if (set.set.chain && set.set.contract && avatar.tokenId) {
    keys.push({
      kind: 'chain-contract-token',
      value: `${normalizeChain(set.set.chain)}:${normalizeContract(set.set.contract)}:${avatar.tokenId.trim()}`,
      priority: 1,
    });
  }
  if (avatar.id) keys.push({ kind: 'source-asset', value: `legacy-altiico:${avatar.id}`, priority: 2 });
  if (avatar.originalSourceUrl) keys.push({ kind: 'source-uri', value: avatar.originalSourceUrl.trim(), priority: 3 });
  return keys;
}
