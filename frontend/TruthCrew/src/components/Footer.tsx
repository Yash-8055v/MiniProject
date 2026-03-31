import { Link } from 'react-router-dom';
import { Shield, Send, Github, ExternalLink } from 'lucide-react';

const NAV_LINKS = [
  { to: '/', label: 'Home' },
  { to: '/analyze', label: 'Analyze Text' },
  { to: '/media', label: 'Analyze Media' },
  { to: '/trending', label: 'Trending' },
  { to: '/about', label: 'About' },
];

const POWERED_BY = [
  { label: 'CrewAI', color: 'text-purple-400 bg-purple-500/10 border-purple-500/20' },
  { label: 'Groq', color: 'text-orange-400 bg-orange-500/10 border-orange-500/20' },
  { label: 'Sarvam AI', color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  { label: 'Llama 4', color: 'text-green-400 bg-green-500/10 border-green-500/20' },
  { label: 'MongoDB', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  { label: 'Google Trends', color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' },
];

const Footer = () => {
  return (
    <footer className="relative mt-auto border-t border-border/20">
      {/* Subtle top glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/2 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

      <div className="bg-background/60 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 pt-14 pb-8">

          {/* Main grid */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-10 mb-12">

            {/* Brand — 5 cols */}
            <div className="md:col-span-5 space-y-5">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                  <Shield className="w-4 h-4 text-primary" />
                </div>
                <span className="text-xl font-bold text-foreground tracking-tight">
                  Truth<span className="text-primary">Crew</span>
                </span>
              </div>

              <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
                An agentic AI framework for multimodal misinformation detection,
                verification, and awareness — built for India's linguistic diversity.
              </p>

              {/* Hindi tagline */}
              <p className="text-sm font-semibold text-primary/80 devanagari tracking-wide">
                रुकें। सोचें। जाँचें।
              </p>

              {/* Telegram CTA */}
              <a
                href="https://t.me/Truth_Crew_Bot"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#2AABEE]/10 border border-[#2AABEE]/25 text-[#2AABEE] text-sm font-medium hover:bg-[#2AABEE]/20 hover:border-[#2AABEE]/50 transition-all duration-200"
              >
                <Send className="w-3.5 h-3.5 fill-[#2AABEE] -rotate-12" />
                Try on Telegram
                <ExternalLink className="w-3 h-3 opacity-60" />
              </a>
            </div>

            {/* Quick Links — 3 cols */}
            <div className="md:col-span-3 space-y-4">
              <h4 className="text-xs font-semibold text-foreground/50 uppercase tracking-widest">
                Navigate
              </h4>
              <ul className="space-y-2.5">
                {NAV_LINKS.map(({ to, label }) => (
                  <li key={to}>
                    <Link
                      to={to}
                      className="text-sm text-muted-foreground hover:text-primary transition-colors duration-200 flex items-center gap-1.5 group"
                    >
                      <span className="w-1 h-1 rounded-full bg-primary/40 group-hover:bg-primary transition-colors duration-200" />
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Built by — 4 cols */}
            <div className="md:col-span-4 space-y-4">
              <h4 className="text-xs font-semibold text-foreground/50 uppercase tracking-widest">
                Powered By
              </h4>
              <div className="flex flex-wrap gap-2">
                {POWERED_BY.map(({ label, color }) => (
                  <span
                    key={label}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium border ${color}`}
                  >
                    {label}
                  </span>
                ))}
              </div>

              <div className="pt-2 space-y-1.5">
                <p className="text-xs text-muted-foreground/70 leading-relaxed">
                  B.Tech AI &amp; Data Science
                </p>
                <p className="text-xs text-muted-foreground/50">
                  National Level Project Showcase
                </p>
              </div>

              <a
                href="https://github.com/Yash-8055v/MiniProject"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors duration-200 group"
              >
                <Github className="w-3.5 h-3.5" />
                View Source on GitHub
                <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-60 transition-opacity duration-200" />
              </a>
            </div>
          </div>

          {/* Divider */}
          <div className="h-px bg-gradient-to-r from-transparent via-border/40 to-transparent mb-6" />

          {/* Bottom bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground/40">
              © {new Date().getFullYear()} TruthCrew · All rights reserved
            </p>
            <p className="text-xs text-muted-foreground/40 text-center">
              Stopping misinformation before it causes harm
            </p>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <p className="text-xs text-muted-foreground/40">
                System operational
              </p>
            </div>
          </div>

        </div>
      </div>
    </footer>
  );
};

export default Footer;
