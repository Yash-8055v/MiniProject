import { Link } from 'react-router-dom';
import { ArrowRight, Shield, AlertTriangle, Users, Send } from 'lucide-react';
import LeafletHeatmap from '../components/LeafletHeatmap';

const Home = () => {
  return (
    <div className="page-transition min-h-screen pt-24 pb-16">
      <div className="max-w-6xl mx-auto px-6">
        {/* Hero Section */}
        <section className="text-center mb-20">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-8">
            <Shield className="w-4 h-4" />
            AI-Powered Verification
          </div>

          <h1 className="text-4xl sm:text-5xl md:text-7xl font-bold text-foreground mb-6 tracking-tight">
            Truth<span className="text-gradient">Crew</span>
          </h1>

          <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
            Stopping Misinformation Before It Causes Harm
          </p>

          {/* Hindi Tagline */}
          <div className="my-16">
            <p className="text-3xl sm:text-5xl md:text-7xl font-extrabold devanagari text-gradient glow-text leading-tight pt-6">
              रुकें। सोचें। जाँचें।
            </p>
          </div>

          {/* Intro Text */}
          <div className="glass-card p-10 max-w-3xl mx-auto mb-12">
            <p className="text-lg text-foreground/80 leading-relaxed mb-5">
              Misinformation spreads faster than truth, especially during emergencies.
              False news can trigger panic, confusion, and dangerous decisions.
            </p>
            <p className="text-lg text-foreground font-medium leading-relaxed">
              TruthCrew encourages people to pause, think, and verify before sharing.
            </p>
          </div>
        </section>

        {/* Impact Stats */}
        <section className="grid md:grid-cols-3 gap-6 mb-20">
          <div className="glass-card-hover p-6 text-center">
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-6 h-6 text-primary" />
            </div>
            <h3 className="text-3xl font-bold text-foreground mb-2">68%</h3>
            <p className="text-muted-foreground text-sm">
              of Indians have encountered fake news online
            </p>
          </div>
          <div className="glass-card-hover p-6 text-center">
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center mx-auto mb-4">
              <Users className="w-6 h-6 text-primary" />
            </div>
            <h3 className="text-3xl font-bold text-foreground mb-2">1.2B+</h3>
            <p className="text-muted-foreground text-sm">
              messages shared daily on messaging platforms
            </p>
          </div>
          <div className="glass-card-hover p-6 text-center">
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center mx-auto mb-4">
              <Shield className="w-6 h-6 text-primary" />
            </div>
            <h3 className="text-3xl font-bold text-foreground mb-2">5x</h3>
            <p className="text-muted-foreground text-sm">
              faster spread of false news vs. verified news
            </p>
          </div>
        </section>

        {/* CTA Section */}
        <section className="mb-20 text-center">
          <div className="glass-card p-12 max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-foreground mb-4">
              Ready to verify a claim?
            </h2>
            <p className="text-muted-foreground mb-8">
              Check any news headline or viral message to understand its current verification status.
            </p>
            <Link to="/analyze" className="btn-primary inline-flex items-center gap-2">
              Analyze a News Claim
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </section>

        {/* Telegram Bot CTA Section */}
        <section className="mb-20">
          <a
            href="https://t.me/Truth_Crew_Bot"
            target="_blank"
            rel="noopener noreferrer"
            className="block group"
          >
            <div
              className="relative overflow-hidden rounded-2xl border border-[#2AABEE]/30 bg-card/60 backdrop-blur-xl shadow-2xl transition-all duration-300 hover:border-[#2AABEE]/60 hover:shadow-[0_0_60px_-10px_rgba(34,158,217,0.35)]"
              style={{ background: 'linear-gradient(135deg, hsl(240 10% 8% / 0.95) 0%, hsl(200 70% 8% / 0.6) 100%)' }}
            >
              {/* Decorative Telegram glow blob */}
              <div className="pointer-events-none absolute -top-16 -right-16 w-64 h-64 rounded-full bg-[#2AABEE]/10 blur-3xl" />
              <div className="pointer-events-none absolute -bottom-10 -left-10 w-48 h-48 rounded-full bg-[#229ED9]/8 blur-2xl" />

              <div className="relative flex flex-col md:flex-row items-center gap-8 p-8 md:p-10">
                {/* Icon */}
                <div className="flex-shrink-0 relative">
                  {/* Pulse ring */}
                  <div className="absolute inset-0 rounded-full bg-[#2AABEE] animate-pulse-ring opacity-30" />
                  <div className="relative w-20 h-20 rounded-2xl bg-gradient-to-tr from-[#229ED9] to-[#2AABEE] flex items-center justify-center shadow-lg shadow-[#229ED9]/40 group-hover:scale-105 transition-transform duration-300">
                    <Send className="w-9 h-9 text-white fill-white -rotate-12 ml-[-3px] mt-[3px]" />
                  </div>
                </div>

                {/* Text Content */}
                <div className="flex-1 text-center md:text-left">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#2AABEE]/10 border border-[#2AABEE]/25 text-[#2AABEE] text-xs font-semibold uppercase tracking-widest mb-3">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#2AABEE] opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-[#2AABEE]" />
                    </span>
                    Now on Telegram
                  </div>
                  <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
                    Verify Claims Directly on{' '}
                    <span style={{ color: '#2AABEE' }}>Telegram</span>
                  </h2>
                  <p className="text-muted-foreground text-base max-w-xl">
                    Send any news headline to our bot and get an instant AI-powered fact-check — without leaving Telegram. Fast, free, and private.
                  </p>
                </div>

                {/* CTA Button */}
                <div className="flex-shrink-0">
                  <div className="inline-flex items-center gap-3 px-7 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-[#229ED9] to-[#2AABEE] shadow-lg shadow-[#229ED9]/30 group-hover:shadow-[#229ED9]/50 group-hover:scale-[1.04] active:scale-[0.97] transition-all duration-300">
                    <Send className="w-4 h-4 fill-white -rotate-12" />
                    Open Bot
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform duration-200" />
                  </div>
                </div>
              </div>
            </div>
          </a>
        </section>

        {/* India Map Section */}
        <section className="mb-20">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-foreground mb-4">
              How Misinformation Spreads Across India
            </h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              This overview visualizes how misinformation affects regions differently
              and why early verification matters.
            </p>
          </div>

          <div className="glass-card p-0 overflow-hidden ring-1 ring-white/10 shadow-2xl">
            <div className="h-[500px] w-full relative">
              <LeafletHeatmap 
                data={{
                  "delhi": 95,
                  "maharashtra": 88,
                  "west bengal": 72,
                  "karnataka": 78,
                  "kerala": 65,
                  "tamil nadu": 62,
                  "uttar pradesh": 58,
                  "gujarat": 50,
                  "rajasthan": 52,
                  "bihar": 45,
                  "telangana": 68,
                  "punjab": 42
                }}
                isLoading={false}
                claim="General Misinformation Trends"
              />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default Home;
