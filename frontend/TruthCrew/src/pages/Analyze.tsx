import { useState } from 'react';
import { Search, CheckCircle, XCircle, HelpCircle, Loader2, AlertTriangle, Gauge, ExternalLink, ShieldCheck, Globe } from 'lucide-react';
import LanguageSelector from '../components/LanguageSelector';
import LeafletHeatmap from '../components/LeafletHeatmap';
import type { HeatmapPoint } from '../components/LeafletHeatmap';
import TopRegionsPanel from '../components/TopRegionsPanel';
import HeatmapInsight from '../components/HeatmapInsight';
import { verifyNews, fetchHeatmap, type VerifyResponse, type Source } from '../services/api';

type VerdictType = 'likely_true' | 'likely_false' | 'likely_misleading' | 'unverified';
type Language = 'en' | 'hi' | 'mr';

/** Map backend verdict string to internal type */
function mapVerdict(raw: string): VerdictType {
  const v = raw.toLowerCase().trim();
  if (v.includes('likely true')) return 'likely_true';
  if (v.includes('likely false')) return 'likely_false';
  if (v.includes('likely misleading') || v.includes('misleading')) return 'likely_misleading';
  return 'unverified';
}

const Analyze = () => {
  const [claim, setClaim] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [verdict, setVerdict] = useState<VerdictType | null>(null);
  const [apiResult, setApiResult] = useState<VerifyResponse | null>(null);
  const [selectedLang, setSelectedLang] = useState<Language>('en');
  const [error, setError] = useState<string | null>(null);
  const [showAllSources, setShowAllSources] = useState(false);
  const [heatmapData, setHeatmapData] = useState<Record<string, number> | null>(null);
  const [isHeatmapLoading, setIsHeatmapLoading] = useState(false);
  const [heatmapError, setHeatmapError] = useState(false);
  const [selectedRegion, setSelectedRegion] = useState<HeatmapPoint | null>(null);

  const analyzeClaim = async () => {
    const text = claim.trim();
    if (!text) return;

    setIsAnalyzing(true);
    setVerdict(null);
    setApiResult(null);
    setSelectedLang('en');
    setError(null);
    setShowAllSources(false);
    setHeatmapData(null);
    setIsHeatmapLoading(true);
    setHeatmapError(false);
    setSelectedRegion(null);

    try {
      const result = await verifyNews(text);
      setApiResult(result);
      setVerdict(mapVerdict(result.verdict));

      // Fire heatmap fetch in parallel (non-blocking)
      fetchHeatmap(text)
        .then((data) => setHeatmapData(data))
        .catch(() => setHeatmapError(true))
        .finally(() => setIsHeatmapLoading(false));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Something went wrong. Please try again.';
      setError(message);
      setIsHeatmapLoading(false);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getExplanation = (lang: Language): string => {
    if (!apiResult) return '';
    if (lang === 'hi') return apiResult.hindi;
    if (lang === 'mr') return apiResult.marathi;
    return apiResult.english;
  };

  const getResultIcon = () => {
    switch (verdict) {
      case 'likely_true':
        return <CheckCircle className="w-6 h-6 text-green-400" />;
      case 'likely_false':
        return <XCircle className="w-6 h-6 text-red-400" />;
      case 'likely_misleading':
        return <AlertTriangle className="w-6 h-6 text-yellow-400" />;
      case 'unverified':
        return <HelpCircle className="w-6 h-6 text-gray-400" />;
      default:
        return null;
    }
  };

  const getResultBadge = () => {
    switch (verdict) {
      case 'likely_true':
        return <span className="badge-verified">{getResultIcon()} Likely True</span>;
      case 'likely_false':
        return <span className="badge-misleading">{getResultIcon()} Likely False</span>;
      case 'likely_misleading':
        return <span className="badge-unverified">{getResultIcon()} Likely Misleading</span>;
      case 'unverified':
        return (
          <span className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold bg-gray-500/20 text-gray-400 border border-gray-500/30">
            {getResultIcon()} Unverified
          </span>
        );
      default:
        return null;
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 70) return 'bg-green-500';
    if (confidence >= 40) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="page-transition min-h-screen pt-24 pb-16">
      <div className="max-w-4xl mx-auto px-6">
        {/* Header */}
        <section className="text-center mb-12 animate-fade-up">
          <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
            Check a News Claim
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Put any news or viral message below to understand its current status.
          </p>
        </section>

        {/* Input Section */}
        <section className="mb-12 animate-fade-up" style={{ animationDelay: '0.1s' }}>
          <div className="glass-card p-8 transition-all duration-300 hover:shadow-xl">
            <div className="relative mb-6">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                value={claim}
                onChange={(e) => setClaim(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && analyzeClaim()}
                placeholder="Enter a news headline or message…"
                className="input-dark pl-12 transition-all duration-200 focus:shadow-lg"
              />
            </div>

            <button
              onClick={analyzeClaim}
              disabled={!claim.trim() || isAnalyzing}
              className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 hover:shadow-2xl"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Analyzing…
                </>
              ) : (
                'Analyze Claim'
              )}
            </button>
          </div>
        </section>

        {/* Image Analysis — Coming Soon */}
        <section className="mb-12 animate-fade-up" style={{ animationDelay: '0.15s' }}>
          <div className="glass-card p-8 opacity-60">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-foreground">Image Analysis</h2>
                <p className="text-sm text-muted-foreground">Coming soon — Image verification will be available in a future update.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Error State */}
        {error && (
          <section className="mb-12 animate-fade-up">
            <div className="glass-card p-8 border-red-500/30 bg-red-500/5">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
                  <XCircle className="w-5 h-5 text-red-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-2">Analysis Failed</h3>
                  <p className="text-muted-foreground">{error}</p>
                  <p className="text-sm text-muted-foreground/60 mt-2">
                    Make sure the backend server is running and try again.
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Results Section */}
        {verdict && apiResult && (
          <section className="animate-fade-up space-y-8">
            <div className="glass-card p-8 transition-all duration-500">
              {/* Verdict Badge */}
              <div className="text-center mb-8 animate-scale-in">
                {getResultBadge()}
              </div>

              {/* Confidence Score */}
              <div className="glass-card p-6 bg-secondary/50 mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <Gauge className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                    Confidence Score
                  </h3>
                  <span className="ml-auto text-lg font-bold text-foreground">
                    {apiResult.confidence}%
                  </span>
                </div>
                <div className="w-full h-3 bg-secondary rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-1000 ease-out ${getConfidenceColor(apiResult.confidence)}`}
                    style={{ width: `${apiResult.confidence}%` }}
                  />
                </div>
              </div>

              {/* Language Selector */}
              <div className="flex justify-center mb-6">
                <LanguageSelector
                  selected={selectedLang}
                  onChange={(lang) => setSelectedLang(lang)}
                />
              </div>

              {/* Explanation */}
              <div className="animate-fade-up space-y-5">
                <div className="glass-card p-7 bg-secondary/50 transition-all duration-300 hover:bg-secondary/70">
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
                    Explanation
                  </h3>
                  <p className={`text-foreground/90 text-lg leading-relaxed ${selectedLang !== 'en' ? 'devanagari' : ''}`}>
                    {getExplanation(selectedLang)}
                  </p>
                </div>

                <div className="glass-card p-7 bg-primary/10 border-primary/20 transition-all duration-300 hover:bg-primary/15">
                  <p className={`text-foreground font-medium leading-relaxed ${selectedLang !== 'en' ? 'devanagari' : ''}`}>
                    {selectedLang === 'hi'
                      ? 'कृपया कोई भी जानकारी साझा करने से पहले विश्वसनीय स्रोतों से सत्यापित करें।'
                      : selectedLang === 'mr'
                        ? 'कृपया कोणतीही माहिती शेअर करण्यापूर्वी विश्वासार्ह स्रोतांकडून पडताळणी करा.'
                        : 'Always verify information from trusted sources before sharing.'}
                  </p>
                </div>
              </div>

              {/* Sources Used */}
              {apiResult.sources && apiResult.sources.length > 0 && (
                <div className="glass-card p-7 bg-secondary/50 transition-all duration-300 hover:bg-secondary/70 mt-5">
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
                    Sources Used for Verification
                  </h3>
                  <ul className="space-y-2">
                    {(showAllSources ? apiResult.sources : apiResult.sources.slice(0, 5)).map(
                      (src: Source, idx: number) => (
                        <li key={idx}>
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-start gap-3 group rounded-lg p-2 -mx-2 hover:bg-muted/30 transition-colors duration-200"
                          >
                            <div className="flex-shrink-0 mt-0.5">
                              {src.trusted ? (
                                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                              ) : (
                                <Globe className="w-4 h-4 text-muted-foreground/50" />
                              )}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-medium text-foreground/90 group-hover:text-primary transition-colors duration-200 leading-snug line-clamp-2">
                                {src.title || src.source}
                              </p>
                              <p className="text-xs text-muted-foreground/60 mt-0.5 flex items-center gap-1">
                                {src.source}
                                {src.trusted && (
                                  <span className="text-emerald-400 font-semibold"> · Trusted</span>
                                )}
                              </p>
                            </div>
                            <ExternalLink className="w-3.5 h-3.5 text-muted-foreground/40 group-hover:text-primary flex-shrink-0 mt-1 transition-colors duration-200" />
                          </a>
                        </li>
                      )
                    )}
                  </ul>
                  {apiResult.sources.length > 5 && (
                    <button
                      onClick={() => setShowAllSources((v) => !v)}
                      className="mt-4 text-xs text-primary hover:text-primary/80 font-medium transition-colors duration-200"
                    >
                      {showAllSources
                        ? 'Show less'
                        : `Show ${apiResult.sources.length - 5} more source${apiResult.sources.length - 5 > 1 ? 's' : ''}`}
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* ============================================================ */}
            {/*  Rumor Spread Heatmap — Leaflet + OpenStreetMap               */}
            {/* ============================================================ */}
            <div className="glass-card p-8 animate-fade-up" style={{ animationDelay: '0.3s' }}>
              <h2 className="text-xl font-bold text-foreground text-center mb-2">
                Spread of this claim across India
              </h2>
              <p className="text-center text-sm text-muted-foreground mb-6">
                Regional search interest based on Google Trends
              </p>

              <div className={`grid gap-8 items-start ${
                heatmapData && Object.keys(heatmapData).length > 0 ? 'lg:grid-cols-[1fr_320px]' : ''
              }`}>
                <LeafletHeatmap
                  data={heatmapData}
                  isLoading={isHeatmapLoading}
                  claim={claim}
                  onRegionClick={(region) => setSelectedRegion(region)}
                />
                {!isHeatmapLoading && heatmapData !== null && (
                  <TopRegionsPanel
                    query={claim}
                    data={heatmapData}
                    isLoading={isHeatmapLoading}
                  />
                )}
                {isHeatmapLoading && (
                  <TopRegionsPanel query={claim} data={{}} isLoading={true} />
                )}
              </div>

              {/* AI Insight */}
              {!isHeatmapLoading && heatmapData && Object.keys(heatmapData).length > 0 && (
                <div className="mt-6">
                  <HeatmapInsight query={claim} data={heatmapData} />
                </div>
              )}
            </div>

            {/* Region detail popup */}
            {selectedRegion && (
              <div className="glass-card p-6 animate-fade-up border-primary/20 bg-primary/5">
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-lg font-bold text-foreground">{selectedRegion.name}</h3>
                  <button
                    onClick={() => setSelectedRegion(null)}
                    className="text-muted-foreground hover:text-foreground transition-colors text-sm"
                  >
                    ✕
                  </button>
                </div>
                <div className="space-y-2 text-sm text-muted-foreground">
                  <p>
                    <span className="text-foreground font-medium">Claim:</span> "{claim}"
                  </p>
                  <p>
                    <span className="text-foreground font-medium">Trend Score:</span>{' '}
                    <span style={{ color: selectedRegion.value >= 70 ? '#ef4444' : selectedRegion.value >= 40 ? '#f97316' : '#94a3b8' }}>
                      {selectedRegion.value}
                    </span>
                    {' '}({selectedRegion.value >= 70 ? 'High' : selectedRegion.value >= 40 ? 'Medium' : 'Low'} intensity)
                  </p>
                  <p className="text-muted-foreground/80 text-xs mt-3 italic">
                    High scores indicate elevated search interest and potential viral spread in this region.
                  </p>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Empty State */}
        {!verdict && !isAnalyzing && !error && (
          <section className="text-center py-12 animate-fade-up" style={{ animationDelay: '0.2s' }}>
            <div className="w-20 h-20 rounded-full bg-secondary flex items-center justify-center mx-auto mb-6 transition-all duration-300 hover:scale-105 hover:bg-secondary/80">
              <Search className="w-10 h-10 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground">
              Enter a claim above to check its verification status
            </p>
          </section>
        )}
      </div>
    </div>
  );
};

export default Analyze;
