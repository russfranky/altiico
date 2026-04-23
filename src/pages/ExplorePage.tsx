import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';

export default function ExplorePage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="border-b border-border bg-card/30">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
            <Link to="/" className="hover:text-foreground transition-colors">
              Home
            </Link>
            <span>/</span>
            <span className="text-primary font-medium">Explore</span>
          </nav>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">
            Explore
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Indexed assets and collections
          </p>
        </div>
      </div>

      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid sm:grid-cols-2 lg:grid-cols-2 gap-6 max-w-2xl">
          <Link to="/explore/assets/avatars">
            <Card className="group p-8 hover:border-primary/50 hover:shadow-lg transition-all cursor-pointer">
              <CardContent className="p-0">
                <h2 className="text-xl font-semibold text-foreground group-hover:text-primary transition-colors">
                  Assets
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Browse indexed avatar assets
                </p>
                <span className="inline-block mt-4 text-sm text-primary font-medium group-hover:underline">
                  View avatars →
                </span>
              </CardContent>
            </Card>
          </Link>
          <Link to="/explore/collections">
            <Card className="group p-8 hover:border-primary/50 hover:shadow-lg transition-all cursor-pointer">
              <CardContent className="p-0">
                <h2 className="text-xl font-semibold text-foreground group-hover:text-primary transition-colors">
                  Collections
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Browse indexed collections
                </p>
                <span className="inline-block mt-4 text-sm text-primary font-medium group-hover:underline">
                  View collections →
                </span>
              </CardContent>
            </Card>
          </Link>
        </div>
      </div>
    </div>
  );
}
