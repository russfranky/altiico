import type { AvatarSetDetail, AvatarSetSummary } from '../../../domain';
import { foundationSet01 } from './set-01';
import { foundationSet02 } from './set-02';
import { foundationSet03 } from './set-03';
import { foundationSet04 } from './set-04';

export const avatarSetDetailFixtures: readonly AvatarSetDetail[] = [foundationSet01, foundationSet02, foundationSet03, foundationSet04];

export function toAvatarSetSummary(item: AvatarSetDetail): AvatarSetSummary {
  const { longDescription: _longDescription, identity: _identity, evidence: _evidence, avatarSlots: _avatarSlots, ...summary } = item;
  return summary;
}
