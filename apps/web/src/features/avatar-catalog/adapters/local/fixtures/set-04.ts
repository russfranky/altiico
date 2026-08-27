import type { AvatarSetDetail } from '../../../domain';
import { fixtureFreshnessLabel, fixtureLicenseLabel, fixtureProvenance } from './constants';

export const foundationSet04 = {
  id: 'fixture-set-04', slug: 'foundation-set-04', displayName: 'Foundation Set 04', archiveCode: 'SET_04.D',
  description: 'A second ready fixture used to test catalog scanning and filter behavior.',
  longDescription: 'Foundation Set 04 provides a compact ready-state example so the detail route can prove consistent hierarchy across different set sizes.',
  state: 'published', readiness: 'ready', avatarCountLabel: '02 LOCAL SLOTS', imageSrc: '/brand/entity-shoulder.png',
  imageAlt: 'Altiico shoulder detail used as a local catalog fixture', tags: ['identity', 'ready'], provenance: fixtureProvenance,
  identity: { sourceSystem: 'local-fixture', sourceCollectionId: 'fixture-set-04', chain: null, contractAddress: null },
  evidence: { provenance: fixtureProvenance, verificationStatus: 'partial', validationScopeLabel: 'STRUCTURE ONLY', licenseLabel: fixtureLicenseLabel, licenseReviewRequired: true, freshnessLabel: fixtureFreshnessLabel, warningLabels: ['fixture_only'] },
  avatarSlots: [
    { slotId: 'slot-01', productAvatarId: 'fixture-avatar-10', avatarSlug: 'ready-01', displayLabel: 'READY ENTITY / 01', sourceAssetId: 'local-reference/entity-shoulder', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-shoulder.png', imageAlt: 'Altiico shoulder detail', formatLabel: 'REFERENCE IMAGE', readiness: 'ready', verificationStatus: 'partial' },
    { slotId: 'slot-02', productAvatarId: 'fixture-avatar-11', avatarSlug: 'ready-02', displayLabel: 'READY ENTITY / 02', sourceAssetId: 'local-reference/entity-face', apiAvatarId: null, tokenId: null, imageSrc: '/brand/entity-face.png', imageAlt: 'Altiico face detail', formatLabel: 'REFERENCE IMAGE', readiness: 'ready', verificationStatus: 'partial' },
  ],
} satisfies AvatarSetDetail;
