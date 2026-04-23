/**
 * API configuration for the avatar service.
 *
 * Set VITE_AVATAR_API in your .env to override the default.
 * Example:  VITE_AVATAR_API=https://api.altiico.com
 */
export const API_BASE_URL =
  import.meta.env.VITE_AVATAR_API || 'http://localhost:1233';
