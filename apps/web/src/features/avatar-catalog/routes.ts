export function avatarSetRoute(setSlug: string) {
  return `/explore/avatar-sets/${setSlug}`;
}

export function avatarDetailRoute(setSlug: string, avatarSlug: string) {
  return `${avatarSetRoute(setSlug)}/avatars/${avatarSlug}`;
}
