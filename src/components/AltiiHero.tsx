import { Link } from 'react-router-dom';

export default function AltiiHero() {
  return (
    <section className="relative overflow-hidden bg-background">
      {/* Subtle honeycomb grid pattern */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='49' viewBox='0 0 28 49'%3E%3Cg fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M13.99 9.25l13 7.5v15l-13 7.5L1 31.75v-15l12.99-7.5zM3 17.9v12.7l10.99 6.34 11-6.35V17.9l-11-6.34L3 17.9zM0 15l12.98-7.5V0h-2v6.35L0 12.69v2.3zm0 18.5L12.98 41v8h-2v-6.85L0 35.81v-2.3zM15 0v7.5L27.99 15H28v-2.31h-.01L17 6.35V0h-2zm0 49v-8l12.99-7.5H28v2.31h-.01L17 42.15V49h-2z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
      }} />

      <div className="relative max-w-7xl mx-auto px-4 py-24 sm:py-32">
        <div className="max-w-2xl">
          {/* Factory badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-3 py-1 text-xs text-muted-foreground mb-6">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-yellow-500 animate-pulse" />
            Avatar factory online
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-foreground leading-[1.1]">
            Your alter ego
            <br />
            starts here.
          </h1>

          <p className="mt-5 text-lg text-muted-foreground max-w-lg leading-relaxed">
            Step into the lobby. Pick a cartridge. Slot it into the printer.
            Walk out as someone entirely new. No name tags &mdash; just style.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/collections"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Browse the cartridges
            </Link>
            <Link
              to="/avatars"
              className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-2.5 text-sm font-medium text-foreground hover:bg-muted/50 transition-colors"
            >
              See the lineup
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
