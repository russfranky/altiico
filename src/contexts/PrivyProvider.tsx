import { PrivyProvider as PrivyAuthProvider } from '@privy-io/react-auth';
import { resolvePrivyAppId } from '@/config/privy';

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
      {children}
    </PrivyAuthProvider>
  );
}
