import { useState, useEffect } from 'react';
import { TrendingUp, ShieldAlert, ExternalLink, MapPin, Calendar, AlertTriangle, Loader2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface TrendingClaim {
  _id: string;
  claim: string;
  explanation: string;
  category: string;
  misleading_score: number;
  source_name: string;
  source_url: string;
  region: string;
  published_at: string;
  created_at: string;
}

function getScoreBadge(score: number): { label: string; className: string } {
  if (score >= 85) return { label: 'False', className: 'badge-false' };
  if (score >= 70) return { label: 'Misleading', className: 'badge-misleading-orange' };
  return { label: 'Unverified', className: 'badge-unverified-yellow' };
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('en-IN', {
      day: 'numeric', month: 'long', year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

function ClaimCard({ claim, index }: { claim: TrendingClaim; index: number }) {
  const { label, className } = getScoreBadge(claim.misleading_score);
  const date = formatDate(claim.published_at || claim.created_at);

  return (
    <div
      className="glass-card-hover p-6 flex flex-col gap-4"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      {/* Top row — badge + category */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className={`status-badge ${className}`}>{label}</span>
        <span className="category-pill">{claim.category}</span>
      </div>

      {/* Claim */}
      <div className="flex gap-3 items-start">
        <ShieldAlert className="w-5 h-5 text-primary mt-0.5 shrink-0" />
        <p className="text-foreground font-semibold text-base leading-snug">
          &ldquo;{claim.claim}&rdquo;
        </p>
      </div>

      {/* Explanation */}
      <p className="text-muted-foreground text-sm leading-relaxed">{claim.explanation}</p>

      {/* Score bar */}
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
          <span>Misleading Score</span>
          <span className="font-semibold text-foreground">{claim.misleading_score}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${claim.misleading_score}%`,
              background:
                claim.misleading_score >= 85
                  ? 'hsl(0 72% 51%)'
                  : claim.misleading_score >= 70
                  ? 'hsl(38 92% 50%)'
                  : 'hsl(48 96% 53%)',
            }}
          />
        </div>
      </div>

      {/* Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-border/40 text-xs text-muted-foreground">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="flex items-center gap-1.5 capitalize">
            <MapPin className="w-3.5 h-3.5" />
            {claim.region}
          </span>
          {claim.source_url ? (
            <a
              href={claim.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-primary hover:text-primary/80 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {claim.source_name}
            </a>
          ) : (
            <span>{claim.source_name}</span>
          )}
        </div>
        <span className="flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5" />
          {date}
        </span>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="glass-card p-6 animate-pulse space-y-4">
      <div className="flex justify-between">
        <div className="h-5 w-20 bg-secondary/80 rounded-full" />
        <div className="h-5 w-16 bg-secondary/80 rounded-full" />
      </div>
      <div className="space-y-2">
        <div className="h-4 bg-secondary/80 rounded w-full" />
        <div className="h-4 bg-secondary/80 rounded w-5/6" />
      </div>
      <div className="space-y-1.5">
        <div className="h-3 bg-secondary/60 rounded w-full" />
        <div className="h-3 bg-secondary/60 rounded w-4/5" />
      </div>
      <div className="h-1.5 bg-secondary/60 rounded-full" />
    </div>
  );
}

const Trending = () => {
  const [claims, setClaims] = useState<TrendingClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchClaims = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/api/trending-claims`);
        if (!res.ok) throw new Error(`Server error: ${res.status}`);
        const json = await res.json();
        // Show only top 5
        setClaims((json.data ?? []).slice(0, 5));
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to fetch claims');
      } finally {
        setLoading(false);
      }
    };

    fetchClaims();
  }, []);

  return (
    <div className="page-transition min-h-screen pt-24 pb-16">
      <div className="max-w-4xl mx-auto px-6">

        {/* Header */}
        <section className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-6">
            <TrendingUp className="w-4 h-4" />
            Updated daily • Powered by AI
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold text-foreground mb-4 tracking-tight">
            Trending <span className="text-gradient">Misinformation</span>
          </h1>

          <p className="text-lg text-muted-foreground max-w-xl mx-auto">
            Top false &amp; misleading claims spreading across India and globally right now.
          </p>
        </section>

        {/* Content */}
        {loading ? (
          <div className="space-y-6">
            <div className="flex items-center justify-center gap-2 text-muted-foreground text-sm mb-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Fetching latest claims…
            </div>
            {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : error ? (
          <div className="glass-card border-red-500/30 p-8 text-center">
            <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-4" />
            <p className="text-red-400 font-semibold mb-1">Could not load claims</p>
            <p className="text-muted-foreground text-sm">{error}</p>
          </div>
        ) : claims.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-5">
              <TrendingUp className="w-8 h-8 text-primary/60" />
            </div>
            <h3 className="text-xl font-semibold text-foreground mb-2">No Claims Yet</h3>
            <p className="text-muted-foreground text-sm max-w-md mx-auto">
              The system is analysing today's news. Check back in a few minutes —
              the pipeline runs automatically every 24 hours.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {claims.map((claim, i) => (
              <ClaimCard key={claim._id} claim={claim} index={i} />
            ))}
            <p className="text-center text-xs text-muted-foreground pt-2">
              Showing top {claims.length} trending claims · Refreshed every 24 hours
            </p>
          </div>
        )}

      </div>
    </div>
  );
};

export default Trending;
