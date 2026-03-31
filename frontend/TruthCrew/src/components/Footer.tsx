import { Link } from 'react-router-dom';
import { Shield } from 'lucide-react';

const Footer = () => {
  return (
    <footer className="border-t border-border/30 bg-background/50 backdrop-blur-sm mt-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">

          {/* Brand */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" />
              <span className="font-bold text-foreground text-lg">TruthCrew</span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              AI-powered misinformation detection for India.
              Supporting Hindi, Marathi & English.
            </p>
          </div>

          {/* Navigation */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Navigate
            </h4>
            <ul className="space-y-2">
              {[
                { to: '/', label: 'Home' },
                { to: '/analyze', label: 'Analyze Claim' },
                { to: '/media', label: 'Media Verification' },
                { to: '/trending', label: 'Trending Claims' },
                { to: '/about', label: 'About' },
              ].map(({ to, label }) => (
                <li key={to}>
                  <Link
                    to={to}
                    className="text-sm text-muted-foreground hover:text-primary transition-colors duration-200"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Team */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Team
            </h4>
            <p className="text-sm text-muted-foreground">
              Built by students of<br />
              <span className="text-foreground/80 font-medium">
                B.Tech AI &amp; Data Science
              </span>
            </p>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary transition-colors duration-200"
            >
              GitHub →
            </a>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-8 pt-6 border-t border-border/20 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground/60">
          <p>© {new Date().getFullYear()} TruthCrew. Built for national showcase.</p>
          <p>Powered by CrewAI · Groq · Sarvam AI · HuggingFace</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
