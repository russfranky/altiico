import { HomeDiscoverySection } from '../components/home-discovery-section';
import { HomeFlowSection } from '../components/home-flow-section';
import { HomeFooter } from '../components/home-footer';
import { HomeHero } from '../components/home-hero';
import { HomeIdentityBand } from '../components/home-identity-band';
import { HomeOperationsSection } from '../components/home-operations-section';
import { HomeRouteSection } from '../components/home-route-section';
import { HomeSystemGrid } from '../components/home-system-grid';
import { HomeVerificationSection } from '../components/home-verification-section';

export function HomeScreen() {
  return (
    <>
      <HomeHero />
      <HomeSystemGrid />
      <HomeIdentityBand />
      <HomeDiscoverySection />
      <HomeVerificationSection />
      <HomeOperationsSection />
      <HomeFlowSection />
      <HomeRouteSection />
      <HomeFooter />
    </>
  );
}
