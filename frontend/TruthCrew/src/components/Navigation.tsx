import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, Menu, X, ArrowRight } from 'lucide-react';

const NAV_LINKS = [
  { path: '/', label: 'Home' },
  { path: '/analyze', label: 'Analyze Text' },
  { path: '/media', label: 'Analyze Media' },
  { path: '/trending', label: 'Trending' },
  { path: '/about', label: 'About' },
];

const Navigation = () => {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  // Add shadow + stronger blur once user scrolls
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => setMobileOpen(false), [location.pathname]);

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  const onAnalyzePage = location.pathname === '/analyze';

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-background/90 backdrop-blur-2xl border-b border-border/40 shadow-[0_1px_40px_rgba(0,0,0,0.3)]'
          : 'bg-background/60 backdrop-blur-xl border-b border-border/20'
      }`}
    >
      {/* Top glow line */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 group flex-shrink-0">
            <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center group-hover:bg-primary/20 group-hover:border-primary/40 transition-all duration-200">
              <Shield className="w-4 h-4 text-primary" />
            </div>
            <span className="text-lg font-bold tracking-tight text-foreground">
              Truth<span className="text-primary">Crew</span>
            </span>
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={`relative px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 group ${
                  isActive(link.path)
                    ? 'text-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
                }`}
              >
                {link.label}
                {/* Active underline indicator */}
                {isActive(link.path) && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4/5 h-0.5 rounded-full bg-primary" />
                )}
              </Link>
            ))}
          </div>

          {/* Right side — CTA + hamburger */}
          <div className="flex items-center gap-3">
            {/* CTA button — hidden on analyze page */}
            {!onAnalyzePage && (
              <Link
                to="/analyze"
                className="hidden md:inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-all duration-200 shadow-[0_0_15px_hsl(0_65%_45%_/_0.35)] hover:shadow-[0_0_25px_hsl(0_65%_45%_/_0.5)]"
              >
                Analyze
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            )}

            {/* Hamburger */}
            <button
              onClick={() => setMobileOpen((prev) => !prev)}
              className="md:hidden p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-border/20 bg-background/95 backdrop-blur-2xl animate-fade-up">
          <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-1">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={`px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 flex items-center justify-between ${
                  isActive(link.path)
                    ? 'bg-primary/10 text-primary border border-primary/20'
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
                }`}
              >
                {link.label}
                {isActive(link.path) && (
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                )}
              </Link>
            ))}
            <Link
              to="/analyze"
              className="mt-2 px-4 py-3 rounded-lg bg-primary text-primary-foreground text-sm font-semibold flex items-center justify-center gap-2"
            >
              Analyze a Claim
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navigation;
