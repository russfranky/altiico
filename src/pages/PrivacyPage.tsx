import { Link } from 'react-router-dom';
import PageSection from '../components/layout/PageSection';

export default function PrivacyPage() {
  return (
    <PageSection>
      <div className="max-w-2xl">
        <h1 className="text-2xl font-bold text-foreground mb-6">Privacy Policy</h1>
        <p className="text-sm text-muted-foreground mb-6">
          Last updated: 2024
        </p>
        <div className="prose prose-invert prose-sm max-w-none text-muted-foreground space-y-4">
          <p>
            Altii.co is a static information site. We do not collect personal data beyond what your
            browser sends by default (e.g. for analytics if enabled).
          </p>
          <p>
            External links (OpenSea, Etherscan, GitHub, etc.) have their own privacy policies.
            We are not responsible for third-party data practices.
          </p>
          <p>
            Newsletter signup, when available, is optional and subject to the provider&apos;s terms.
          </p>
        </div>
        <Link to="/" className="inline-block mt-8 text-sm text-primary hover:underline">
          ← Back to home
        </Link>
      </div>
    </PageSection>
  );
}
