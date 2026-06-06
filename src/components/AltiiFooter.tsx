import { Link } from 'react-router-dom';

const AltiiFooter = () => {
  return (
    <footer className="border-t border-border bg-muted/30">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">altiico</span>
            <span className="text-muted-foreground/50">/</span>
            <span>avatar factory</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-muted-foreground">
            <Link to="/explore/collections" className="hover:text-foreground transition-colors">
              Avatar Sets
            </Link>
            <Link to="/explore/assets/avatars" className="hover:text-foreground transition-colors">
              Avatars
            </Link>
            <span>&copy; {new Date().getFullYear()} altiico &middot; a hive operation</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default AltiiFooter;
