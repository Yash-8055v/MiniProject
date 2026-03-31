import type { CredibilityLayers } from '../services/api';

interface ScoreBreakdownProps {
  layers: CredibilityLayers;
  finalScore: number;
}

const LAYER_LABELS: Record<keyof CredibilityLayers, string> = {
  source_tier: 'Source Quality',
  source_count: 'Sources Found',
  evidence_alignment: 'Evidence Match',
  claim_verifiability: 'Claim Clarity',
  cross_agreement: 'Source Agreement',
};

function barColor(score: number): string {
  if (score >= 70) return 'bg-green-500';
  if (score >= 40) return 'bg-yellow-500';
  return 'bg-red-500';
}

function scoreLabel(score: number): string {
  if (score >= 70) return 'text-green-400';
  if (score >= 40) return 'text-yellow-400';
  return 'text-red-400';
}

const ScoreBreakdown = ({ layers, finalScore }: ScoreBreakdownProps) => {
  const layerOrder: (keyof CredibilityLayers)[] = [
    'source_tier',
    'source_count',
    'evidence_alignment',
    'claim_verifiability',
    'cross_agreement',
  ];

  return (
    <div className="glass-card p-6 bg-secondary/50">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
        Credibility Score Breakdown
      </h3>

      <div className="space-y-3">
        {layerOrder.map((key) => {
          const layer = layers[key];
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-muted-foreground">
                  {LAYER_LABELS[key]}
                  <span className="ml-1 text-muted-foreground/50">[{layer.weight}%]</span>
                </span>
                <span className={`text-xs font-semibold ${scoreLabel(layer.score)}`}>
                  {layer.score}%
                </span>
              </div>
              <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000 ease-out ${barColor(layer.score)}`}
                  style={{ width: `${layer.score}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Divider + Final Score */}
      <div className="mt-4 pt-4 border-t border-border/30 flex items-center justify-between">
        <span className="text-sm font-semibold text-foreground">Final Credibility Score</span>
        <span className={`text-lg font-bold ${scoreLabel(finalScore)}`}>
          {finalScore}%
        </span>
      </div>
    </div>
  );
};

export default ScoreBreakdown;
