import * as Sentry from '@sentry/react';

// Sentry init runs before any React import so errors during hydration are
// captured. DSN absent when the env var is unset (fresh clone, CI build
// without secrets) — init becomes a no-op, no crash, no noise.
if (import.meta.env.VITE_SENTRY_DSN_ALTIICO) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN_ALTIICO,
    environment: import.meta.env.VITE_APP_ENV ?? import.meta.env.MODE,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: import.meta.env.VITE_APP_ENV === 'production' ? 0.1 : 1.0,
    sendDefaultPii: true,
    // Noise filter parity with hubzz-alpha/packages/client + /packages/admin.
    // Altiico does not use Privy today; keeping the entry here means when a
    // shared auth SDK lands the filter list stays identical across apps.
    ignoreErrors: [
      /cannot dequeue privy:iframe:ready event/,
    ],
  });
  Sentry.setTag('service', 'altiico');
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// Load Inter font asynchronously so it doesn't block first paint.
// The browser will use the system sans-serif fallback until the font loads.
import('@fontsource-variable/inter');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
