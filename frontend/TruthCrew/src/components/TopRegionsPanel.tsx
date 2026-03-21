import { Flame, AlertTriangle, Circle, TrendingUp, Info } from 'lucide-react';

interface TopRegionsPanelProps {
  query: string;
  data: Record<string, number>;
  isLoading: boolean;
}

function getIntensityLabel(score: number): { label: string; emoji: string; color: string } {
  if (score >= 70) return { label: 'High', emoji: '🔴', color: '#ef4444' };
  if (score >= 40) return { label: 'Medium', emoji: '🟠', color: '#f97316' };
  return { label: 'Low', emoji: '⚪', color: '#94a3b8' };
}

const capitalize = (s: string) =>
  s.split(' ').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

export default function TopRegionsPanel({ query, data, isLoading }: TopRegionsPanelProps) {
  if (isLoading) {
    return (
      <div className="glass-card p-6 border-primary/20 bg-primary/5 space-y-4 animate-pulse">
        <div className="h-5 bg-muted rounded w-2/3" />
        <div className="h-4 bg-muted rounded w-full" />
        <div className="h-4 bg-muted rounded w-5/6" />
        <div className="h-4 bg-muted rounded w-3/4" />
        <div className="h-4 bg-muted rounded w-2/3" />
        <div className="h-4 bg-muted rounded w-1/2" />
      </div>
    );
  }

  const entries = Object.entries(data)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  if (!query || entries.length === 0) {
    return (
      <div className="glass-card p-6 text-center text-muted-foreground">
        <Info className="w-5 h-5 mx-auto mb-2 opacity-60" />
        <p className="text-sm">No significant regional trend detected for this claim.</p>
      </div>
    );
  }

  const maxScore = entries[0]?.[1] ?? 100;

  return (
    <div className="glass-card p-6 text-left space-y-5 relative overflow-hidden bg-primary/5 border-primary/20">
      {/* Background icon */}
      <div className="absolute top-0 right-0 p-4 opacity-[0.04] pointer-events-none">
        <TrendingUp className="w-24 h-24" />
      </div>

      {/* Header */}
      <div>
        <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
          <Flame className="w-5 h-5 text-primary" />
          Most Affected Regions
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          Search interest for: <span className="text-foreground font-medium">"{query}"</span>
        </p>
      </div>

      {/* Ranked list */}
      <div className="space-y-3">
        {entries.map(([state, score], idx) => {
          const intensity = getIntensityLabel(score);
          return (
            <div key={state} className="region-rank-item">
              {/* Rank number */}
              <div className="region-rank-number">{idx + 1}</div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-semibold text-foreground truncate">
                    {capitalize(state)}
                  </span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs font-bold" style={{ color: intensity.color }}>
                      {score}
                    </span>
                    <span
                      className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                      style={{
                        backgroundColor: `${intensity.color}20`,
                        color: intensity.color,
                      }}
                    >
                      {intensity.emoji} {intensity.label}
                    </span>
                  </div>
                </div>

                {/* Score bar */}
                <div className="w-full h-1.5 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{
                      width: `${(score / maxScore) * 100}%`,
                      backgroundColor: intensity.color,
                      boxShadow: `0 0 8px ${intensity.color}60`,
                    }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
