import type { AvatarSlotSummary } from '../domain';

export type AvatarSiblingSelection = {
  previous: AvatarSlotSummary | null;
  next: AvatarSlotSummary | null;
};

export function selectAvatarSiblings(slots: readonly AvatarSlotSummary[], avatarSlug: string): AvatarSiblingSelection {
  const index = slots.findIndex((slot) => slot.avatarSlug === avatarSlug);
  if (index < 0) return { previous: null, next: null };
  return {
    previous: index > 0 ? slots[index - 1] : null,
    next: index < slots.length - 1 ? slots[index + 1] : null,
  };
}
