import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePrivy, useLogin, useLogout } from '@privy-io/react-auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import {
  submitCollection,
  fetchMySubmissions,
  type Submission,
  type SubmissionInput,
} from '@/services/submissionsService';

const SLUG_PATTERN = /^[a-z0-9-]+$/;

type FormState = {
  name: string;
  slug: string;
  description: string;
  contract: string;
  chain: 'ethereum' | 'somnia' | 'polygon' | 'base';
  source: 'ethereum' | 'opensource' | 'zora' | 'arweave';
  license: string;
  banner_url: string;
  pfp_url: string;
};

const INITIAL: FormState = {
  name: '',
  slug: '',
  description: '',
  contract: '',
  chain: 'ethereum',
  source: 'ethereum',
  license: '',
  banner_url: '',
  pfp_url: '',
};

function toInput(f: FormState): SubmissionInput {
  const input: SubmissionInput = {
    name: f.name.trim(),
    slug: f.slug.trim().toLowerCase(),
    chain: f.chain,
    source: f.source,
  };
  if (f.description.trim()) input.description = f.description.trim();
  if (f.contract.trim()) input.contract = f.contract.trim();
  if (f.license.trim()) input.license = f.license.trim();
  if (f.banner_url.trim()) input.banner_url = f.banner_url.trim();
  if (f.pfp_url.trim()) input.pfp_url = f.pfp_url.trim();
  return input;
}

function validate(f: FormState): string | null {
  if (!f.name.trim()) return 'Name is required';
  if (f.name.trim().length > 80) return 'Name must be 80 characters or fewer';
  if (!f.slug.trim()) return 'Slug is required';
  if (f.slug.trim().length > 40) return 'Slug must be 40 characters or fewer';
  if (!SLUG_PATTERN.test(f.slug.trim().toLowerCase())) {
    return 'Slug may only contain lowercase letters, digits, and hyphens';
  }
  if (f.contract.trim() && !/^0x[a-fA-F0-9]{40}$/.test(f.contract.trim())) {
    return 'Contract must be a 0x-prefixed 40-char hex string';
  }
  return null;
}

function StatusBadge({ status }: { status: Submission['status'] }) {
  const colorMap: Record<Submission['status'], string> = {
    draft: 'bg-muted text-muted-foreground',
    under_review: 'bg-amber-500/20 text-amber-400',
    approved: 'bg-emerald-500/20 text-emerald-400',
    rejected: 'bg-red-500/20 text-red-400',
  };
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded ${colorMap[status]}`}>
      {status.replace('_', ' ')}
    </span>
  );
}

function AuthGate({ onLogin }: { onLogin: () => void }) {
  return (
    <Card className="p-12 text-center space-y-4">
      <h2 className="text-xl font-semibold text-foreground">Sign in to submit a collection</h2>
      <p className="text-sm text-muted-foreground max-w-md mx-auto">
        Creator submissions are linked to your wallet or social identity so you can track review
        status and re-submit with changes if needed. Public pages on altii.co remain open to
        everyone.
      </p>
      <Button onClick={onLogin}>Sign in</Button>
    </Card>
  );
}

export default function SubmitPage() {
  const { ready, authenticated, user, getAccessToken } = usePrivy();
  const { login } = useLogin();
  const { logout } = useLogout();

  const [form, setForm] = useState<FormState>(INITIAL);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
  const [mine, setMine] = useState<Submission[]>([]);
  const [loadingMine, setLoadingMine] = useState(false);

  async function refreshMine() {
    if (!authenticated) return;
    const token = await getAccessToken();
    if (!token) return;
    setLoadingMine(true);
    try {
      setMine(await fetchMySubmissions(token));
    } finally {
      setLoadingMine(false);
    }
  }

  useEffect(() => {
    if (authenticated) refreshMine();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);

    const err = validate(form);
    if (err) {
      setMessage({ kind: 'error', text: err });
      return;
    }

    const token = await getAccessToken();
    if (!token) {
      setMessage({ kind: 'error', text: 'Sign-in expired. Please sign in again.' });
      return;
    }

    setSubmitting(true);
    try {
      const result = await submitCollection(toInput(form), token);
      if (result.ok === true) {
        setMessage({
          kind: 'success',
          text: `Submitted as draft. Tracking id: ${result.submission.id}`,
        });
        setForm(INITIAL);
        refreshMine();
      } else {
        const err = result.error;
        const fieldErrors = err.fields
          ? Object.entries(err.fields).map(([k, v]) => `${k}: ${v}`).join(', ')
          : null;
        setMessage({
          kind: 'error',
          text:
            fieldErrors ||
            err.message ||
            `Submission failed (${result.status} ${err.error})`,
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center">
        <div className="text-sm text-muted-foreground">Loading…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-card/30">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
            <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
            <span>/</span>
            <span className="text-primary font-medium">Submit a collection</span>
          </nav>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground">Submit a collection</h1>
              <p className="text-sm text-muted-foreground mt-1 max-w-xl">
                Propose an avatar set for hubzz. Submissions start as drafts and are reviewed before
                going live. You can track status on this page.
              </p>
            </div>
            {authenticated && (
              <Button variant="ghost" size="sm" onClick={() => logout()}>
                Sign out
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {!authenticated ? (
          <AuthGate onLogin={() => login()} />
        ) : (
          <>
            <Card className="p-6">
              <div className="mb-4">
                <div className="text-xs text-muted-foreground">Signed in as</div>
                <div className="text-sm font-medium text-foreground break-all">
                  {user?.email?.address ??
                    user?.wallet?.address ??
                    user?.google?.email ??
                    user?.id}
                </div>
              </div>

              <form className="space-y-4" onSubmit={handleSubmit}>
                <div>
                  <label className="text-xs font-medium text-foreground mb-1 block">
                    Collection name *
                  </label>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Cool Cats"
                    maxLength={80}
                    required
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground mb-1 block">
                    Slug *
                  </label>
                  <Input
                    value={form.slug}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, slug: e.target.value.toLowerCase() }))
                    }
                    placeholder="cool-cats"
                    pattern="[a-z0-9-]+"
                    maxLength={40}
                    required
                  />
                  <div className="text-[11px] text-muted-foreground mt-1">
                    Lowercase letters, digits, hyphens. Used in URLs and R2 paths.
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-foreground mb-1 block">Chain</label>
                    <select
                      className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                      value={form.chain}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, chain: e.target.value as FormState['chain'] }))
                      }
                    >
                      <option value="ethereum">Ethereum</option>
                      <option value="somnia">Somnia</option>
                      <option value="polygon">Polygon</option>
                      <option value="base">Base</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-foreground mb-1 block">Source</label>
                    <select
                      className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                      value={form.source}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, source: e.target.value as FormState['source'] }))
                      }
                    >
                      <option value="ethereum">Ethereum (NFT)</option>
                      <option value="opensource">Open source</option>
                      <option value="zora">Zora</option>
                      <option value="arweave">Arweave</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground mb-1 block">
                    Contract (optional)
                  </label>
                  <Input
                    value={form.contract}
                    onChange={(e) => setForm((f) => ({ ...f, contract: e.target.value }))}
                    placeholder="0x…"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground mb-1 block">
                    License (optional)
                  </label>
                  <Input
                    value={form.license}
                    onChange={(e) => setForm((f) => ({ ...f, license: e.target.value }))}
                    placeholder="CC0, CC-BY-4.0, etc."
                    maxLength={80}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground mb-1 block">
                    Description (optional)
                  </label>
                  <textarea
                    className="w-full min-h-[90px] rounded-md border border-input bg-background p-3 text-sm"
                    value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    maxLength={2000}
                    placeholder="What is this collection? Who is it for?"
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-foreground mb-1 block">
                      Banner URL (optional)
                    </label>
                    <Input
                      value={form.banner_url}
                      onChange={(e) => setForm((f) => ({ ...f, banner_url: e.target.value }))}
                      placeholder="https://…/banner.png"
                      type="url"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-foreground mb-1 block">
                      PFP URL (optional)
                    </label>
                    <Input
                      value={form.pfp_url}
                      onChange={(e) => setForm((f) => ({ ...f, pfp_url: e.target.value }))}
                      placeholder="https://…/pfp.png"
                      type="url"
                    />
                  </div>
                </div>

                <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
                  {submitting ? 'Submitting…' : 'Submit as draft'}
                </Button>

                {message && (
                  <div
                    className={`text-sm px-3 py-2 rounded-md ${
                      message.kind === 'success'
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'bg-red-500/10 text-red-400'
                    }`}
                  >
                    {message.text}
                  </div>
                )}
              </form>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-foreground">Your submissions</h2>
                <Button variant="ghost" size="sm" onClick={refreshMine} disabled={loadingMine}>
                  {loadingMine ? 'Refreshing…' : 'Refresh'}
                </Button>
              </div>
              {mine.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  You have no submissions yet. Use the form above to create one.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {mine.map((s) => (
                    <li key={s.id} className="py-3 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-foreground truncate">
                          {s.name}
                        </div>
                        <div className="text-xs text-muted-foreground font-mono">{s.slug}</div>
                        {s.review_notes && (
                          <div className="text-xs text-muted-foreground mt-1 italic">
                            Note: {s.review_notes}
                          </div>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <StatusBadge status={s.status} />
                        <div className="text-[11px] text-muted-foreground mt-1">
                          {new Date(s.submitted_at).toLocaleDateString()}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
