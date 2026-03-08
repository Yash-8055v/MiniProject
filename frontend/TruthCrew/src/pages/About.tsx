import { Shield, Heart, Users, CheckCircle } from 'lucide-react';

const About = () => {
  return (
    <div className="page-transition min-h-screen pt-24 pb-16">
      <div className="max-w-4xl mx-auto px-6">
        {/* Header */}
        <section className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-6">
            <Heart className="w-4 h-4" />
            Our Purpose
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-6">
            Our Mission
          </h1>
        </section>

        {/* Mission Content */}
        <section className="mb-16">
          <div className="glass-card p-10 text-center">
            <p className="text-xl text-foreground mb-6 leading-relaxed">
              <span className="text-primary font-semibold">Misinformation is not harmless.</span>
              <br />
              It creates fear, panic, and wrong actions.
            </p>
            <p className="text-lg text-muted-foreground mb-8 leading-relaxed">
              During emergencies, even a single false message can cause chaos.
            </p>
            <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent my-8" />
            <p className="text-xl text-foreground font-medium">
              TruthCrew exists to slow the spread of misinformation
              and help people <span className="text-gradient">think before they share</span>.
            </p>
          </div>
        </section>

        {/* Impact Section */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-foreground text-center mb-8">
            When people verify before sharing:
          </h2>

          <div className="grid md:grid-cols-3 gap-6">
            <div className="glass-card-hover p-6 text-center">
              <div className="w-14 h-14 rounded-xl bg-green-500/20 border border-green-500/30 flex items-center justify-center mx-auto mb-4">
                <Shield className="w-7 h-7 text-green-400" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Panic Reduces
              </h3>
              <p className="text-muted-foreground text-sm">
                Communities stay calm and make rational decisions during crises
              </p>
            </div>

            <div className="glass-card-hover p-6 text-center">
              <div className="w-14 h-14 rounded-xl bg-blue-500/20 border border-blue-500/30 flex items-center justify-center mx-auto mb-4">
                <Users className="w-7 h-7 text-blue-400" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Trust Increases
              </h3>
              <p className="text-muted-foreground text-sm">
                People rely on verified sources and build stronger social bonds
              </p>
            </div>

            <div className="glass-card-hover p-6 text-center">
              <div className="w-14 h-14 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-7 h-7 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Lives Are Saved
              </h3>
              <p className="text-muted-foreground text-sm">
                Timely, accurate information leads to better decisions
              </p>
            </div>
          </div>
        </section>

        {/* SDG 16 Section */}
        <section className="mb-16">
          <div className="glass-card p-8">
            <div className="flex items-start gap-6">
              <div className="w-16 h-16 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center flex-shrink-0">
                <span className="text-2xl font-bold text-primary">16</span>
              </div>
              <div>
                <h3 className="text-xl font-bold text-foreground mb-2">
                  SDG 16: Peace, Justice & Strong Institutions
                </h3>
                <p className="text-muted-foreground leading-relaxed">
                  TruthCrew aligns with the United Nations Sustainable Development Goal 16,
                  which promotes peaceful and inclusive societies, access to justice for all,
                  and building effective, accountable institutions at all levels.
                  Combating misinformation is essential for maintaining public trust and social harmony.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Closing Tagline */}
        <section className="text-center">
          <div className="glass-card p-12 bg-gradient-to-b from-card to-primary/5">
            <blockquote className="text-2xl md:text-3xl font-semibold text-foreground leading-relaxed">
              "In the right moment, the right information
              <span className="text-gradient block mt-2">can save lives."</span>
            </blockquote>
          </div>
        </section>

        {/* Team Credit */}
        <section className="mt-12 text-center">
          <p className="text-muted-foreground text-sm">
            Awareness before amplification
          </p>
          <p className="text-foreground font-semibold mt-2">
            Team LeoForge
          </p>
        </section>
      </div>
    </div>
  );
};

export default About;
