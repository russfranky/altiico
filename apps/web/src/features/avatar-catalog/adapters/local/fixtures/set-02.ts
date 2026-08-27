import type { AvatarSetDetail } from '../../../domain';
import { fixtureFreshnessLabel, fixtureLicenseLabel, fixtureProvenance } from './constants';

export const foundationSet02 = {
  id: 'fixture-set-02', slug: 'foundation-set-02', displayName: 'Foundation Set 02', archiveCode: 'SET_02.B',
  description: 'A local fixture for staged-set states, metadata density, and responsive card behavior.',
  longDescription: 'Foundation Set 02 demonstrates a staged collection that still needs review. It remains intentionally disconnected from chain, contract, and production catalog identity.',
  state: 'staged', readiness: 'review', avatarCountLabel: '03 LOCAL SLOTS', imageSrc: '/brand/entity-face.png',
  imageAlt: 'Altiico face detail used as a local catalog fixture', tags: ['portrait', 'staged'], provenance: fixtureProvenance,
  identity: { sourceSystem: 'local-fixture', sourceCollectionId: 'fixture-set-02', chain: null, contractAddress: null },
  evidence: { provenance: fixtureProvenance, verificationStatus: 'partial', validationScopeLabel: 'STRUCTURE ONLY', licenseLabel: fixtureLicenseLabel, licenseReviewRequired: true, freshnessLabel: fixtureFreshnessLabel, warningLabels: ['fixture_only', 'review_state'] },
  avatarSlots: [
    { slotId: 'slot-01', productAvatarId: 'fixture-avatar-05', avatarSlug: 'portrait-01', displayLabel: 'PORTRAIT / 01', sourceAssetId: 'local-reference/entity-face', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-face.png', imageAlt: 'Altiico face detail', formatLabel: 'REFERENCE IMAGE', readiness: 'review', verificationStatus: 'partial' },
    { slotId: 'slot-02', productAvatarId: 'fixture-avatar-06', avatarSlug: 'portrait-02', displayLabel: 'PORTRAIT / 02', sourceAssetId: 'local-reference/entity-detail', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-detail.png', imageAlt: 'Altiico entity detail', formatLabel: 'REFERENCE IMAGE', readiness: 'review', verificationStatus: 'partial' },
    { slotId: 'slot-03', productAvatarId: 'fixture-avatar-07', avatarSlug: 'portrait-03', displayLabel: 'PORTRAIT / 03', sourceAssetId: 'local-reference/entity-shoulder', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-shoulder.png', imageAlt: 'Altiico shoulder detail', formatLabel: 'REFERENCE IMAGE', readiness: 'review', verificationStatus: 'unverified' },
  ],
} satisfies AvatarSetDetail;
