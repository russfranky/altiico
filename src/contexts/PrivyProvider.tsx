import { PrivyProvider as PrivyAuthProvider, usePrivy } from '@privy-io/react-auth';
import { useEffect, useRef } from 'react';
import { resolvePrivyAppId } from '@/config/privy';

/**
 * Syncs the Privy login state into the cross-subdomain session cookie.
 *
 * On login: POST the access token to the game server's /api/auth/session,
 * which sets `hubzz_session` scoped to Domain=.hubzz.xyz — so a login here
 * is shared with hubzz.xyz + dash.hubzz.xyz (no re-login). On logout: DELETE.
 *
 * /api/* is same-origin on every *.hubzz.xyz vhost (nginx → game server),
 * so credentials:'include' carries/sets the parent-domain cookie.
 */
function SessionCookieSync() {
  const { ready, authenticated, getAccessToken } = usePrivy();
  const synced = useRef(false);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    (async () => {
      try {
        if (authenticated) {
          if (synced.current) return;
          const token = await getAccessToken();
          if (!token || cancelled) return;
          await fetch('/api/auth/session', {
            method: 'POST',
            credentials: 'include',
            headers: { Authorization: `Bearer ${token}` },
          });
          synced.current = true;
        } else {
          if (synced.current) {
            await fetch('/api/auth/session', { method: 'DELETE', credentials: 'include' });
          }
          synced.current = false;
        }
      } catch {
        /* non-fatal: SSO cookie sync is best-effort; Bearer auth still works */
      }
    })();
    return () => { cancelled = true; };
  }, [ready, authenticated, getAccessToken]);

  return null;
}

/**
 * altiico's Privy wrapper. Configured independently of hubzz-alpha — see
 * `src/config/privy.ts` for app-id resolution. Token storage is in-browser
 * only; avatar-api accepts the resulting JWT via Authorization: Bearer.
 */
export function PrivyProvider({ children }: { children: React.ReactNode }) {
  return (
    <PrivyAuthProvider
      appId={resolvePrivyAppId()}
      config={{
        loginMethods: ['email', 'google', 'discord', 'twitter', 'wallet'],
        appearance: {
          theme: 'dark',
          accentColor: '#735FFA',
        },
        embeddedWallets: {
          ethereum: { createOnLogin: 'users-without-wallets' },
        },
      }}
    >
      <SessionCookieSync />
      {children}
    </PrivyAuthProvider>
  );
}
