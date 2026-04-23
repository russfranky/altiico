import { Link } from 'react-router-dom';
import PageSection from '../components/layout/PageSection';

export default function TermsPage() {
  return (
    <PageSection>
      <div className="max-w-2xl">
        <h1 className="text-2xl font-bold text-foreground mb-6">Terms of Service</h1>
        <p className="text-sm text-muted-foreground mb-6">
          Last updated: 2024
        </p>
        <div className="prose prose-invert prose-sm max-w-none text-muted-foreground space-y-4">
          <p>
            Altii.co is a curated index for 3D digital identities and heritage NFT collections.
            By using this site you agree to use it responsibly and in accordance with applicable laws.
          </p>
          <p>
            Content, collection metadata, and linked external resources (OpenSea, Etherscan, GitHub, etc.)
            are provided for informational purposes. We do not guarantee accuracy of third-party data.
          </p>
          <p>
            For questions, contact us via the channels listed in the footer.
          </p>
        </div>
        <Link to="/" className="inline-block mt-8 text-sm text-primary hover:underline">
          ← Back to home
        </Link>
      </div>
    </PageSection>
  );
}
