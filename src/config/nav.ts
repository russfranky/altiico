/**
 * Central navigation configuration.
 * Keeps navbar, footer, and any other navigation in sync.
 *
 * The Preview route is gated — only shown in dev or when VITE_SHOW_PREVIEW=true.
 * It is never shown on the public nav in production by default (no auth layer —
 * gate at the CDN/nginx level if you expose altiico publicly).
 */

export interface NavItem {
  label: string;
  path: string;
  description: string;
  devOnly?: boolean;
}

export const MAIN_NAV: NavItem[] = [
  { label: 'Explore', path: '/explore', description: 'Indexed assets and collections' },
  { label: 'Collections', path: '/explore/collections', description: 'Indexed collections' },
  {
    label: 'Pipeline',
    path: '/pipeline',
    description: 'Avatar pipeline — end-to-end flow',
    devOnly: true,
  },
  {
    label: 'Preview',
    path: '/preview',
    description: 'QA lab — avatar + animation preview',
    devOnly: true,
  },
];

/** Nav items visible in the current environment */
export const VISIBLE_NAV = MAIN_NAV.filter(
  (item) =>
    !item.devOnly ||
    import.meta.env.DEV ||
    import.meta.env.VITE_SHOW_PREVIEW === 'true'
);
