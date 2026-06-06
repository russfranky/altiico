/**
 * Privy app-id resolution for altiico.
 *
 * Matches the split used by hubzz-alpha/packages/client/src/contexts/Providers.tsx:
 *   - sandbox app: dev, staging (altii.co on dev box, hubzz.xyz), localhost
 *   - prod app:    altii.co on production
 *
 * Override via VITE_PRIVY_APP_ID if you need to point a specific deploy at a
 * non-default app (for example a preview build pointing at a scratch Privy app).
 *
 * Note: altiico intentionally does NOT read hubzz-alpha's packages/server/config.json.
 * altii.co is its own dependency (see memory: project_altiico_independent_dependency).
 */

export const PRIVY_SANDBOX_APP_ID = 'cmmmkrl5a009f0bjo4iupja76';
export const PRIVY_PROD_APP_ID = 'clp0x8o7i00h3jf0fmxlcqrpa';

export function resolvePrivyAppId(): string {
  const override = import.meta.env.VITE_PRIVY_APP_ID;
  if (override) return override;

  if (import.meta.env.DEV) return PRIVY_SANDBOX_APP_ID;

  if (typeof window !== 'undefined') {
    const host = window.location.hostname;

    // avatars.hubzz.xyz is the PRODUCTION avatars site. Its Privy login must
    // use the PROD app so tokens validate against the same app the hubzz
    // server/avatar-api trusts (packages/server/config.json jwks =
    // clp0x8o7i...). Using the sandbox app here logs users into a Privy app
    // the server rejects, so auth can never complete. Match dash.hubzz.xyz /
    // hubzz.xyz, which also use PROD.
    if (host === 'avatars.hubzz.xyz') {
      return PRIVY_PROD_APP_ID;
    }

    // Non-production hostnames use the sandbox app:
    //   - other *.hubzz.xyz (staging)
    //   - localhost / 127.0.0.1
    //   - explore.altii.co (dev-box preview of altiico)
    if (
      host.includes('hubzz.xyz') ||
      host.includes('localhost') ||
      host.includes('127.0.0.1') ||
      host.startsWith('explore.')
    ) {
      return PRIVY_SANDBOX_APP_ID;
    }
  }

  return PRIVY_PROD_APP_ID;
}
