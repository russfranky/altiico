import { Link } from 'react-router-dom';
import { opensourceResources, awesome3dCollections, openSourceAvatarsProjects } from '@/data/altiiData';
import PageSection from '../components/layout/PageSection';

export default function RevivalToolkitPage() {
  return (
    <>
      <PageSection>
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold text-foreground mb-4">Revival Toolkit</h1>
          <p className="text-muted-foreground mb-8">
            Resources to build with and extend the VIPE / CryptoAvatars heritage.
          </p>

          <section className="space-y-6">
            <h2 className="text-lg font-semibold text-foreground">3D Avatar Collections Index</h2>
            <p className="text-sm text-muted-foreground">
              <a href="https://github.com/itsmetamike/awesome-3D-avatar-collections" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                Awesome 3D Avatar Collections
              </a>
              {' '}— tokenized collections on Ethereum with VRM/GLB metadata.
            </p>
            <ul className="space-y-2 text-sm">
              {awesome3dCollections.map((c) => (
                <li key={c.contract}>
                  <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    {c.name}
                  </a>
                  {c.metadataParam && (
                    <span className="text-muted-foreground ml-2">({c.metadataParam})</span>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-12 space-y-6">
            <h2 className="text-lg font-semibold text-foreground">Open Source Avatars Registry</h2>
            <p className="text-sm text-muted-foreground">
              <a href="https://opensourceavatars.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                opensourceavatars.com
              </a>
              {' '}— Free VRM avatars with direct download links. API:{' '}
              <a href="https://raw.githubusercontent.com/ToxSam/open-source-avatars/main/data/projects.json" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline font-mono text-xs">
                projects.json
              </a>
            </p>
            <ul className="space-y-1 text-sm">
              {openSourceAvatarsProjects.map((p) => (
                <li key={p.id}>
                  <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    {p.name}
                  </a>
                  <span className="text-muted-foreground ml-2">{p.license}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-12 space-y-6">
            <h2 className="text-lg font-semibold text-foreground">CC0 Asset Packs</h2>
            <p className="text-sm text-muted-foreground">
              Polygonal Mind&apos;s opensource initiative. Free to use, modify, and distribute.
            </p>
            <ul className="space-y-3">
              {opensourceResources.map((item) => (
                <li key={item.href}>
                  <a
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline font-medium"
                  >
                    {item.label}
                  </a>
                  {item.description && (
                    <span className="text-sm text-muted-foreground ml-2">— {item.description}</span>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-12 space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Protocol & Contracts</h2>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="https://etherscan.io/address/0x3999877754904d8542ad1845d368fa01a5e6e9a5" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  VIPE Heroes (Ethereum)
                </a>
              </li>
              <li>
                <a href="https://polygonscan.com/address/0x3999877754904d8542ad1845d368fa01a5e6e9a5" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  VIPE Heroes (Polygon)
                </a>
              </li>
            </ul>
          </section>

          <section className="mt-12 space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Reference</h2>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="https://vrm.dev/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  VRM specification
                </a>
              </li>
              <li>
                <a href="https://github.com/pixiv/three-vrm" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  three-vrm
                </a>
                <span className="text-muted-foreground ml-1">(web)</span>
              </li>
              <li>
                <a href="https://github.com/vrm-c/UniVRM" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  UniVRM
                </a>
                <span className="text-muted-foreground ml-1">(Unity)</span>
              </li>
              <li>
                <a href="https://github.com/ruyo/VRM4U" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  VRM4U
                </a>
                <span className="text-muted-foreground ml-1">(Unreal)</span>
              </li>
              <li>
                <a href="https://mirror.xyz/m3org.eth/4NPYOzRtcuYHrRI7iZK1yADswgOv9To2ErQ8KrqLPX0" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  3D NFT Metadata
                </a>
              </li>
              <li>
                <a href="https://hackmd.io/@XR/nftavatars" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  3D NFT Avatars
                </a>
              </li>
              <li>
                <a href="https://m3org.com/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  M3 Org Hub
                </a>
              </li>
              <li>
                <a href="https://web.archive.org/web/20240530084427/https://vipe.io/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  Vipe.io archive
                </a>
              </li>
            </ul>
          </section>

          <div className="mt-12 flex gap-4">
            <Link to="/explore/collections" className="text-sm text-primary hover:underline">
              Browse collections
            </Link>
            <Link to="/" className="text-sm text-primary hover:underline">
              Home
            </Link>
          </div>
        </div>
      </PageSection>
    </>
  );
}
