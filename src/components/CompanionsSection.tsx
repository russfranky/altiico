import { companions, PLACEHOLDER_IMG } from '../data/altiiData';
import { ExternalLink } from 'lucide-react';

const onImgError = (e: React.SyntheticEvent<HTMLImageElement>) => {
  e.currentTarget.src = PLACEHOLDER_IMG;
};

export default function CompanionsSection() {
  return (
    <section className="border-t border-border py-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h2 className="text-2xl md:text-3xl font-bold text-foreground">
            Companions
          </h2>
          <p className="text-muted-foreground mt-1">
            Curated projects from the ecosystem
          </p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {companions.map((project) => (
            <a
              key={project.name}
              href={project.href}
              target="_blank"
              rel="noopener noreferrer"
              className="group block rounded-lg border border-border bg-card overflow-hidden hover:border-primary/40 transition-colors"
            >
              <div className="relative aspect-[16/10]">
                <img
                  src={project.banner}
                  alt={project.name}
                  className="w-full h-full object-cover"
                  onError={onImgError}
                />
                <div className="absolute bottom-2 right-2 text-xs font-medium px-2 py-1 rounded bg-background/90 text-foreground">
                  {project.items}
                </div>
              </div>
              <div className="p-3 flex gap-3">
                <img
                  src={project.pfp}
                  alt=""
                  className="w-10 h-10 rounded-lg object-cover border border-border shrink-0"
                  onError={onImgError}
                />
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-foreground truncate text-sm group-hover:text-primary transition-colors">
                    {project.name}
                  </h3>
                  <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                    {project.description}
                  </p>
                  <span className="inline-flex items-center gap-1 text-xs text-primary mt-1">
                    OpenSea
                    <ExternalLink className="size-3" />
                  </span>
                </div>
              </div>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
