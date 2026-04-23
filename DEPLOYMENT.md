# Deployment Guide

The shadcn app is set up for deployment. Choose one of the options below.

## Environment Variables

Required at build time (Vite inlines `VITE_*` vars into the bundle). Configure
these in the deploy platform's environment-variable UI or in a local
`.env.production` / `.env.development` file. **Never commit `.env.*`** — they
are gitignored.

| Variable | Example | Purpose |
|---|---|---|
| `VITE_AVATAR_API` | `/avatar-api` (prod), `http://localhost:1233` (dev) | Base URL for the avatar-api microservice (hubzz-alpha/packages/avatar-api). Use a same-origin proxy path in prod to avoid mixed-content blocks on HTTPS hosts. |
| `VITE_SENTRY_DSN_ALTIICO` | `https://…@o…ingest.us.sentry.io/…` | Sentry project DSN. Obtained from the Sentry UI (hubzz-inc org → altiico project). Missing = Sentry silently disabled. |
| `VITE_APP_ENV` | `development` or `production` | Tags Sentry events by environment. |

Sentry DSNs are intentionally public-side (rate-limited, project-scoped) —
they are not secrets.

## Option 1: Vercel (Recommended - Easiest)

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
2. Click **Add New Project** and import `russfranky/altiico`
3. Vercel auto-detects the Vite config - click **Deploy**
4. Your app will be live at `https://altiico-*.vercel.app`

## Option 2: GitHub Pages

1. In your repo, go to **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Branch: `gh-pages` / `/(root)` → Save
4. The deploy workflow runs on pushes to the default branch and publishes to `gh-pages`
5. Your app will be at `https://russfranky.github.io/altiico/`

## Option 3: Manual Build & Deploy

```bash
npm ci
npm run build
# Upload the `dist/` folder to any static host (Netlify, Cloudflare Pages, etc.)
```
