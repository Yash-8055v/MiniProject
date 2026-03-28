import { Link } from 'react-router-dom';
import { ArrowRight, Shield, AlertTriangle, Users } from 'lucide-react';
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
