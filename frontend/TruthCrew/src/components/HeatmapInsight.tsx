import { useState, useEffect } from 'react';
import { Sparkles, Loader2 } from 'lucide-react';
import { fetchHeatmapInsight } from '../services/api';

interface HeatmapInsightProps {
  query: string;
  data: Record<string, number>;
}

export default function HeatmapInsight({ query, data }: HeatmapInsightProps) {
  const [insight, setInsight] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!query || !data || Object.keys(data).length === 0) {
      setInsight(null);
      return;
    }

    setIsLoading(true);
    setError(false);
    setInsight(null);

    fetchHeatmapInsight(query, data)
      .then((text) => setInsight(text))
      .catch(() => {
        setError(true);
        // Fallback insight
        const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
        const highRegions = entries.filter(([, s]) => s >= 70);
        if (highRegions.length > 0) {
          setInsight(
            `This claim shows significant traction in ${highRegions.length} region${highRegions.length > 1 ? 's' : ''}, suggesting concentrated online activity and engagement in these areas.`
          );
        } else {
          setInsight(
            'This claim shows moderate spread across multiple regions without a single dominant hotspot.'
          );
        }
      })
      .finally(() => setIsLoading(false));
  }, [query, data]);

  if (!query || !data || Object.keys(data).length === 0) return null;

  return (
    <div className="glass-card p-6 bg-gradient-to-br from-primary/8 to-transparent border-primary/15 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-0 right-0 p-3 opacity-[0.04] pointer-events-none">
        <Sparkles className="w-20 h-20" />
      </div>

      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
          <Sparkles className="w-4 h-4 text-primary" />
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
            AI Insight
            {isLoading && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />}
          </h4>
          {isLoading ? (
            <div className="space-y-2 animate-pulse">
              <div className="h-3.5 bg-muted rounded w-full" />
              <div className="h-3.5 bg-muted rounded w-3/4" />
            </div>
          ) : insight ? (
            <p className="text-sm text-muted-foreground leading-relaxed">{insight}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
