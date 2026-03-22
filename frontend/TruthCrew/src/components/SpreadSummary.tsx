import { AlertTriangle, Flame, Info } from 'lucide-react';

interface SpreadSummaryProps {
  query: string;
  data: Record<string, number>;
  isLoading: boolean;
}

export default function SpreadSummary({ query, data, isLoading }: SpreadSummaryProps) {
  if (isLoading) {
    return (
      <div className="glass-card p-6 border-primary/20 bg-primary/5 animate-pulse">
        <div className="h-5 bg-muted rounded w-1/3 mb-4" />
        <div className="h-4 bg-muted rounded w-2/3 mb-2" />
        <div className="h-4 bg-muted rounded w-1/2" />
      </div>
    );
  }

  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);

  // Empty / no-data state
  if (!query || entries.length === 0) {
    return (
      <div className="glass-card p-6 text-center text-muted-foreground">
        <Info className="w-5 h-5 mx-auto mb-2 opacity-60" />
        <p className="text-sm">No significant regional trend detected for this claim.</p>
      </div>
    );
  }

  const high = entries.filter(([, s]) => s >= 70);
  const moderate = entries.filter(([, s]) => s >= 40 && s < 70);

  const capitalize = (s: string) =>
    s.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

  return (
    <div className="glass-card p-6 text-left space-y-4 relative overflow-hidden bg-primary/5 border-primary/20">
      {/* Background icon */}
      <div className="absolute top-0 right-0 p-4 opacity-[0.04] pointer-events-none">
        <Flame className="w-24 h-24" />
      </div>

      <div>
        <h3 className="text-lg font-bold text-foreground">Spread Analysis (India)</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Search interest for: <span className="text-foreground font-medium">"{query}"</span>
        </p>
      </div>

      <div className="space-y-3">
        {high.length > 0 && (
          <div className="flex items-start gap-3">
            <div className="mt-0.5 w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
              <Flame className="w-3.5 h-3.5 text-red-500" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">🔥 High activity in:</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {high.map(([s]) => capitalize(s)).join(', ')}
              </p>
            </div>
          </div>
        )}

        {moderate.length > 0 && (
          <div className="flex items-start gap-3">
            <div className="mt-0.5 w-6 h-6 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">⚠️ Moderate activity in:</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {moderate.map(([s]) => capitalize(s)).join(', ')}
              </p>
            </div>
          </div>
        )}

        {high.length === 0 && moderate.length === 0 && (
          <p className="text-sm text-muted-foreground">All regions show low activity for this claim.</p>
        )}
      </div>
    </div>
  );
}
