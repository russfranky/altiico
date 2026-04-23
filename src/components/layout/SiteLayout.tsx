import { Outlet } from 'react-router-dom';
import AltiiNavbar from '../AltiiNavbar';
import AltiiFooter from '../AltiiFooter';

/**
 * Root layout: Navbar + main content + Footer.
 * All pages render inside <Outlet />.
 */
export default function SiteLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <AltiiNavbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <AltiiFooter />
    </div>
  );
}
