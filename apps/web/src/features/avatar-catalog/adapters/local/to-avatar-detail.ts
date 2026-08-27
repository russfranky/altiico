import type { AvatarDetail, AvatarSetDetail, AvatarSlotSummary } from '../../domain';
import { fixtureProvenance } from './fixtures/constants';
import { toAvatarSetSummary } from './fixtures';

function fixtureTraitValue(slot: AvatarSlotSummary) {
  if (slot.imageSrc.includes('face')) return 'PORTRAIT';
  if (slot.imageSrc.includes('detail')) return 'DETAIL';
  if (slot.imageSrc.includes('shoulder')) return 'SHOULDER';
  return 'FULL ENTITY';
}

export function toLocalAvatarDetail(set: AvatarSetDetail, slot: AvatarSlotSummary): AvatarDetail {
  return {
    productAvatarId: slot.productAvatarId,
    avatarSlug: slot.avatarSlug,
    displayName: slot.displayLabel,
    archiveCode: `${set.archiveCode}.${slot.slotId.replace('slot-', '')}`,
    description: `${slot.displayLabel} is a local structural fixture used to prove the individual-avatar identity and route contract. It is not a live Hubzz avatar record.`,
    imageSrc: slot.imageSrc,
    imageAlt: slot.imageAlt,
    formatLabel: slot.formatLabel,
    readiness: slot.readiness,
    provenance: set.provenance,
    set: toAvatarSetSummary(set),
    identity: {
      productAvatarId: slot.productAvatarId,
      avatarSlug: slot.avatarSlug,
      productSetId: set.id,
      setSlug: set.slug,
      sourceAssetId: slot.sourceAssetId,
      apiAvatarId: slot.apiAvatarId,
      tokenId: slot.tokenId,
      chain: set.identity.chain,
      contractAddress: set.identity.contractAddress,
    },
    evidence: {
      provenance: fixtureProvenance,
      verificationStatus: slot.verificationStatus,
      validationScopeLabel: set.evidence.validationScopeLabel,
      sourceUri: null,
      transportUri: null,
      sourceCheckStatus: null,
      reachable: null,
      vrmSpec: null,
      fileSizeBytes: null,
      checkedAtLabel: 'LOCAL / STATIC',
      warningLabels: ['fixture_only', 'no_binary_claim'],
    },
    traits: [
      { key: 'VISUAL ROLE', value: fixtureTraitValue(slot), provenance: fixtureProvenance },
      { key: 'SOURCE CLASS', value: 'ALTIICO REFERENCE', provenance: fixtureProvenance },
      { key: 'ROUTE STATE', value: 'FOUNDATION', provenance: fixtureProvenance },
    ],
    preview: {
      mode: 'reserved',
      label: '3D PREVIEW / RESERVED',
      note: 'The public avatar route owns the preview entry point. Studio owns engine rendering and QA.',
    },
  };
}
