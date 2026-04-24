import { API_BASE_URL } from '@/config/api';

/**
 * Creator-intake submissions service. Talks HTTP to avatar-api.
 *
 * Contract source of truth: avatar-api's `POST /api/collections/submit` and
 * `GET /api/collections/submissions/mine` (Wave 1, commit b46bfec).
 *
 * altiico does not share types with hubzz-alpha — if the avatar-api endpoint
 * changes shape, update the interfaces below to match. See memory:
 * project_altiico_independent_dependency.
 */

export interface SubmissionInput {
  name: string;
  slug: string;
  description?: string;
  contract?: string;
  chain?: 'ethereum' | 'somnia' | 'polygon' | 'base';
  source?: 'ethereum' | 'opensource' | 'zora' | 'arweave';
  license?: string;
  banner_url?: string;
  pfp_url?: string;
}

export interface Submission {
  id: number;
  slug: string;
  name: string;
  status: 'draft' | 'under_review' | 'approved' | 'rejected';
  submitted_at: string;
  updated_at?: string | null;
  review_notes?: string | null;
}

export interface SubmitError {
  error: string;
  message?: string;
  fields?: Record<string, string>;
}

/**
 * The avatar-api's `/api/collections/submit` endpoint is mounted under the
 * hubzz game-server route prefix. API_BASE_URL in altiico today is e.g.
 * `http://localhost:1233` (avatar-api direct). The submit endpoint is served
 * by the same avatar-api process.
 */
function submitUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export async function submitCollection(
  input: SubmissionInput,
  token: string,
): Promise<{ ok: true; submission: Submission } | { ok: false; error: SubmitError; status: number }> {
  const res = await fetch(submitUrl('/api/collections/submit'), {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });

  if (res.ok) {
    const data = await res.json();
    return { ok: true, submission: data.submission };
  }

  let body: SubmitError;
  try {
    body = await res.json();
  } catch {
    body = { error: 'unknown', message: `HTTP ${res.status}` };
  }
  return { ok: false, error: body, status: res.status };
}

export async function fetchMySubmissions(token: string): Promise<Submission[]> {
  const res = await fetch(submitUrl('/api/collections/submissions/mine'), {
    headers: { authorization: `Bearer ${token}` },
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.submissions ?? [];
}
