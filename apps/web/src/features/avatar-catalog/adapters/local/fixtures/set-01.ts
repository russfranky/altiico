import type { AvatarSetDetail } from '../../../domain';
import { fixtureFreshnessLabel, fixtureLicenseLabel, fixtureProvenance } from './constants';

export const foundationSet01 = {
  id: 'fixture-set-01', slug: 'foundation-set-01', displayName: 'Foundation Set 01', archiveCode: 'SET_01.A',
  description: 'A local fixture used to prove the public catalog structure before live catalog data is connected.',
  longDescription: 'Foundation Set 01 proves the public set-detail contract. It carries identity, evidence, readiness, and avatar-slot structure without making claims about a real collection.',
  state: 'published', readiness: 'ready', avatarCountLabel: '04 LOCAL SLOTS', imageSrc: '/brand/entity-full.png',
  imageAlt: 'Altiico reference entity used as a local catalog fixture', tags: ['identity', 'reference'], provenance: fixtureProvenance,
  identity: { sourceSystem: 'local-fixture', sourceCollectionId: 'fixture-set-01', chain: null, contractAddress: null },
  evidence: { provenance: fixtureProvenance, verificationStatus: 'unverified', validationScopeLabel: 'NO BINARY CLAIM', licenseLabel: fixtureLicenseLabel, licenseReviewRequired: true, freshnessLabel: fixtureFreshnessLabel, warningLabels: ['fixture_only'] },
  avatarSlots: [
    { slotId: 'slot-01', productAvatarId: 'fixture-avatar-01', avatarSlug: 'alt-07-4', displayLabel: 'ALT.07.4', sourceAssetId: 'local-reference/entity-full', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-full.png', imageAlt: 'Full Altiico reference entity', formatLabel: 'REFERENCE IMAGE', readiness: 'ready', verificationStatus: 'unverified' },
    { slotId: 'slot-02', productAvatarId: 'fixture-avatar-02', avatarSlug: 'alt-07-4-face', displayLabel: 'ALT.07.4 / FACE', sourceAssetId: 'local-reference/entity-face', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-face.png', imageAlt: 'Altiico face reference entity', formatLabel: 'REFERENCE IMAGE', readiness: 'ready', verificationStatus: 'unverified' },
    { slotId: 'slot-03', productAvatarId: 'fixture-avatar-03', avatarSlug: 'alt-07-4-detail', displayLabel: 'ALT.07.4 / DETAIL', sourceAssetId: 'local-reference/entity-detail', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-detail.png', imageAlt: 'Altiico detail reference entity', formatLabel: 'REFERENCE IMAGE', readiness: 'review', verificationStatus: 'unverified' },
    { slotId: 'slot-04', productAvatarId: 'fixture-avatar-04', avatarSlug: 'alt-07-4-shoulder', displayLabel: 'ALT.07.4 / SHOULDER', sourceAssetId: 'local-reference/entity-shoulder', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-shoulder.png', imageAlt: 'Altiico shoulder reference entity', formatLabel: 'REFERENCE IMAGE', readiness: 'review', verificationStatus: 'unverified' },
  ],
} satisfies AvatarSetDetail;
