import { lazy, Suspense } from 'react';
import * as Sentry from '@sentry/react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import SiteLayout from './components/layout/SiteLayout';
import PageSkeleton from './components/ui/PageSkeleton';
import ObsOverlay from './components/ObsOverlay';

const HomePage = lazy(() => import('./pages/HomePage'));
const CollectionsPage = lazy(() => import('./pages/CollectionsPage'));
const ExploreAvatarsPage = lazy(() => import('./pages/ExploreAvatarsPage'));
const ExploreCollectionsPage = lazy(() => import('./pages/ExploreCollectionsPage'));
const ExplorePage = lazy(() => import('./pages/ExplorePage'));
const CollectionDetailPage = lazy(() => import('./pages/CollectionDetailPage'));
const AnimationPreviewPage = lazy(() => import('./pages/AnimationPreviewPage'));
const PipelinePage = lazy(() => import('./pages/PipelinePage'));

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
      <Router basename={import.meta.env.BASE_URL}>
        <Suspense fallback={<PageSkeleton />}>
          <Routes>
            <Route element={<SiteLayout />}>
              <Route path="/" element={
                <Suspense fallback={<PageSkeleton />}>
                  <HomePage />
                </Suspense>
              } />
              <Route path="/explore" element={
                <Suspense fallback={<PageSkeleton />}>
                  <ExplorePage />
                </Suspense>
              } />
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
              <Route path="/collections" element={
                <Suspense fallback={<PageSkeleton />}>
                  <CollectionsPage />
                </Suspense>
              } />
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
            </Route>
          </Routes>
        </Suspense>
      </Router>
      <ObsOverlay />
    </Sentry.ErrorBoundary>
  );
}

export default App;
