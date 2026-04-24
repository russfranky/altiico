import { API_BASE_URL } from '@/config/api';

/**
 * Client for POST /api/collections/:slug/thumbnails/:id/pfp on avatar-api.
 * Sends a PNG dataUrl; avatar-api writes to R2 and returns the altii.co URL.
 *
 * Contract source of truth: avatar-api/src/routes/submit.ts
 */

export interface PfpUploadSuccess {
  ok: true;
  url: string;
  key: string;
}

export interface PfpUploadError {
  ok: false;
  status: number;
  error: string;
  message?: string;
}

export type PfpUploadResult = PfpUploadSuccess | PfpUploadError;

export async function uploadPfpThumbnail(
  slug: string,
  avatarId: string | number,
  dataUrl: string,
  token: string,
): Promise<PfpUploadResult> {
  const url = `${API_BASE_URL}/api/collections/${encodeURIComponent(slug)}/thumbnails/${encodeURIComponent(String(avatarId))}/pfp`;

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ dataUrl }),
  });

  if (res.ok) {
    const data = await res.json();
    return { ok: true, url: data.url, key: data.key };
  }

  let body: { error?: string; message?: string } = {};
  try { body = await res.json(); } catch { /* non-JSON */ }
  return {
    ok: false,
    status: res.status,
    error: body.error ?? 'unknown',
    message: body.message,
  };
}
