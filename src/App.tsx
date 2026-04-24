import { lazy, Suspense } from 'react';
import * as Sentry from '@sentry/react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import SiteLayout from './components/layout/SiteLayout';
import PageSkeleton from './components/ui/PageSkeleton';
import ObsOverlay from './components/ObsOverlay';
import { PrivyProvider } from './contexts/PrivyProvider';

const HomePage = lazy(() => import('./pages/HomePage'));
// CollectionsPage and ExplorePage retired — both redirect to /explore/collections.
// ExplorePage was a dead-click 2-card hub; CollectionsPage was a duplicate list
// view. Consolidated in UX audit 2026-04-24 so there's one canonical path to
// the avatar set grid. Old /collections + /explore URLs still 301 so existing
// links / hero CTAs / footer links don't break mid-migration.
const ExploreAvatarsPage = lazy(() => import('./pages/ExploreAvatarsPage'));
const ExploreCollectionsPage = lazy(() => import('./pages/ExploreCollectionsPage'));
const CollectionDetailPage = lazy(() => import('./pages/CollectionDetailPage'));
const AnimationPreviewPage = lazy(() => import('./pages/AnimationPreviewPage'));
const PipelinePage = lazy(() => import('./pages/PipelinePage'));
const SubmitPage = lazy(() => import('./pages/SubmitPage'));

function App() {
  return (
    <Sentry.ErrorBoundary
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background p-6 text-center">
          <div>
            <h1 className="text-xl font-semibold">Something went wrong.</h1>
            <p className="mt-2 text-sm text-muted-foreground">The error has been reported. Try refreshing the page.</p>
          </div>
        </div>
      }
    >
      <PrivyProvider>
      <Router basename={import.meta.env.BASE_URL}>
        <Suspense fallback={<PageSkeleton />}>
          <Routes>
            <Route element={<SiteLayout />}>
              <Route path="/" element={
                <Suspense fallback={<PageSkeleton />}>
                  <HomePage />
                </Suspense>
              } />
              <Route path="/explore" element={<Navigate to="/explore/collections" replace />} />
              <Route path="/explore/assets/avatars" element={
                <Suspense fallback={<PageSkeleton />}>
                  <ExploreAvatarsPage />
                </Suspense>
              } />
              <Route path="/explore/collections" element={
                <Suspense fallback={<PageSkeleton />}>
                  <ExploreCollectionsPage />
                </Suspense>
              } />
              <Route path="/explore/collections/:slug" element={
                <Suspense fallback={<PageSkeleton />}>
                  <CollectionDetailPage />
                </Suspense>
              } />
              <Route path="/collections" element={<Navigate to="/explore/collections" replace />} />
              {/* Preview route — dev/QA only. Gate at CDN/nginx if exposed publicly. */}
              <Route path="/preview" element={
                <Suspense fallback={<PageSkeleton />}>
                  <AnimationPreviewPage />
                </Suspense>
              } />
              <Route path="/pipeline" element={
                <Suspense fallback={<PageSkeleton />}>
                  <PipelinePage />
                </Suspense>
              } />
              <Route path="/submit" element={
                <Suspense fallback={<PageSkeleton />}>
                  <SubmitPage />
                </Suspense>
              } />
            </Route>
          </Routes>
        </Suspense>
      </Router>
      <ObsOverlay />
      </PrivyProvider>
    </Sentry.ErrorBoundary>
  );
}

export default App;
