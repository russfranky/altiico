import type { AvatarSetDetail } from '../../../domain';
import { fixtureFreshnessLabel, fixtureLicenseLabel, fixtureProvenance } from './constants';

export const foundationSet03 = {
  id: 'fixture-set-03', slug: 'foundation-set-03', displayName: 'Foundation Set 03', archiveCode: 'SET_03.C',
  description: 'A local fixture for readiness and review states. It is not a live Hubzz collection.',
  longDescription: 'Foundation Set 03 exists to prove blocked readiness, warnings, and empty external identity fields without turning missing evidence into stronger claims.',
  state: 'review', readiness: 'blocked', avatarCountLabel: '02 LOCAL SLOTS', imageSrc: '/brand/entity-detail.png',
  imageAlt: 'Altiico entity detail used as a local catalog fixture', tags: ['qa', 'review'], provenance: fixtureProvenance,
  identity: { sourceSystem: 'local-fixture', sourceCollectionId: 'fixture-set-03', chain: null, contractAddress: null },
  evidence: { provenance: fixtureProvenance, verificationStatus: 'unverified', validationScopeLabel: 'BLOCKED / NO CLAIM', licenseLabel: fixtureLicenseLabel, licenseReviewRequired: true, freshnessLabel: fixtureFreshnessLabel, warningLabels: ['fixture_only', 'blocked_readiness'] },
  avatarSlots: [
    { slotId: 'slot-01', productAvatarId: 'fixture-avatar-08', avatarSlug: 'qa-01', displayLabel: 'QA ENTITY / 01', sourceAssetId: 'local-reference/entity-detail', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-detail.png', imageAlt: 'Altiico entity detail', formatLabel: 'REFERENCE IMAGE', readiness: 'blocked', verificationStatus: 'unverified' },
    { slotId: 'slot-02', productAvatarId: 'fixture-avatar-09', avatarSlug: 'qa-02', displayLabel: 'QA ENTITY / 02', sourceAssetId: 'local-reference/entity-full', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-full.png', imageAlt: 'Altiico full entity', formatLabel: 'REFERENCE IMAGE', readiness: 'blocked', verificationStatus: 'unverified' },
  ],
} satisfies AvatarSetDetail;
