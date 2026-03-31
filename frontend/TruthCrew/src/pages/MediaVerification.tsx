import { useState, useRef, useEffect } from "react";
import { UploadCloud, Image as ImageIcon, Video, Mic, AlertTriangle, CheckCircle, Loader2, Info, ChevronDown } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";
import LanguageSelector from "@/components/LanguageSelector";
import { detectImageIntelligent, detectVideo, detectAudio, DetectImageResponse, IntelligentDetectResponse } from "@/services/api";

type MediaTab = 'image' | 'video' | 'audio';

const MediaVerification = () => {
  const [activeTab, setActiveTab] = useState<MediaTab>('image');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [result, setResult] = useState<any>(null);
  const [language, setLanguage] = useState<'en' | 'hi' | 'mr'>('en');
  // Intelligent image detection context fields
  const [imgSource, setImgSource] = useState('');
  const [imgDescription, setImgDescription] = useState('');
  const [imgSuspicion, setImgSuspicion] = useState('');
  // Parallel loading simulation
  const [seComplete, setSeComplete] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const MAX_IMAGE_SIZE = 20 * 1024 * 1024;
  const MAX_VIDEO_SIZE = 15 * 1024 * 1024;
  const MAX_AUDIO_SIZE = 10 * 1024 * 1024;

  const ACCEPT_MAP: Record<MediaTab, string> = {
    image: 'image/*',
    video: 'video/*',
    audio: 'audio/*,.mp3,.wav,.ogg,.webm',
  };

  const switchTab = (tab: MediaTab) => {
    setActiveTab(tab);
    setSelectedFile(null);
    setPreviewUrl(null);
    setResult(null);
    setImgSource('');
    setImgDescription('');
    setImgSuspicion('');
  };

  const handleValidFile = (file: File) => {
    const isVideo = file.type.startsWith("video/");
    const isAudio = file.type.startsWith("audio/");
    const limit = isVideo ? MAX_VIDEO_SIZE : isAudio ? MAX_AUDIO_SIZE : MAX_IMAGE_SIZE;
    const label = isVideo ? "videos" : isAudio ? "audio" : "images";
    const maxMB = isVideo ? "15MB" : isAudio ? "10MB" : "5MB";

    if (file.size > limit) {
      toast({
        title: "File too large",
        description: `Max ${maxMB} allowed for ${label}.`,
        variant: "destructive",
      });
      return;
    }

    setSelectedFile(file);
    if (!isAudio) setPreviewUrl(URL.createObjectURL(file));
    setResult(null);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const validType =
      (activeTab === 'image' && file.type.startsWith("image/")) ||
      (activeTab === 'video' && file.type.startsWith("video/")) ||
      (activeTab === 'audio' && file.type.startsWith("audio/"));
    if (!validType) {
      toast({
        title: "Invalid file type",
        description: `Please upload a${activeTab === 'audio' ? 'n audio' : activeTab === 'image' ? 'n image' : ' video'} file.`,
        variant: "destructive",
      });
      return;
    }
    handleValidFile(file);
  };

  const handleDragOver = (e: React.DragEvent) => e.preventDefault();

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    const validType =
      (activeTab === 'image' && file.type.startsWith("image/")) ||
      (activeTab === 'video' && file.type.startsWith("video/")) ||
      (activeTab === 'audio' && file.type.startsWith("audio/"));
    if (validType) handleValidFile(file);
  };

  // When analyzing an image, SightEngine finishes in ~2s — simulate it completing
  useEffect(() => {
    if (isAnalyzing && activeTab === 'image') {
      setSeComplete(false);
      const t = setTimeout(() => setSeComplete(true), 2200);
      return () => clearTimeout(t);
    } else {
      setSeComplete(false);
    }
  }, [isAnalyzing, activeTab]);

  const handleAnalyze = async () => {
    if (!selectedFile) return;
    setIsAnalyzing(true);
    setResult(null);
    try {
      let response: DetectImageResponse | IntelligentDetectResponse;
      if (activeTab === 'audio') {
        response = await detectAudio(selectedFile);
      } else if (activeTab === 'video') {
        response = await detectVideo(selectedFile);
      } else {
        response = await detectImageIntelligent(
          selectedFile,
          imgSource || undefined,
          imgDescription || undefined,
          imgSuspicion || undefined,
        );
      }
      setResult(response);
      toast({ title: "Analysis Complete", description: `${activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} verification finished.` });
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to analyze media.";
      toast({ title: "Analysis Failed", description: msg, variant: "destructive" });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getExplanation = () => {
    if (!result?.explanation) return null;
    switch (language) {
      case 'hi': return result.explanation.hindi;
      case 'mr': return result.explanation.marathi;
      default: return result.explanation.english;
    }
  };

  // Determine UI colors based on verdict (covers intelligent, SightEngine, and audio verdicts)
  const isIntelligent = result && 'verdict_label' in result;
  const isUnavailable = result?.status === "unavailable";
  const isAi = isIntelligent
    ? (result.verdict === 'AI_GENERATED' || result.verdict === 'LIKELY_AI')
    : (result?.verdict === "likely AI-generated" || result?.verdict === "likely AI-generated voice");
  const isUncertain = isIntelligent
    ? result.verdict === 'UNCERTAIN'
    : result?.verdict === "uncertain";
  const verdictDisplay = isIntelligent ? result.verdict_label : result?.verdict ?? '';

  const verdictColor = isUnavailable
    ? "text-muted-foreground"
    : isAi
      ? "text-red-500"
      : isUncertain
        ? "text-orange-500"
        : "text-green-500";

  const bgColor = isUnavailable
    ? "bg-secondary/30 border-border/40"
    : isAi
      ? "bg-red-500/10 border-red-500/20"
      : isUncertain
        ? "bg-orange-500/10 border-orange-500/20"
        : "bg-green-500/10 border-green-500/20";

  return (
    <div className="min-h-screen pt-24 pb-12 px-4 sm:px-6 relative z-10">
      <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
        
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-primary/20 ring-1 ring-primary/30 mb-4 shadow-[0_0_30px_hsl(0_65%_45%_/_0.3)]">
            {activeTab === 'audio' ? <Mic className="w-8 h-8 text-primary" /> : <Video className="w-8 h-8 text-primary" />}
          </div>
          <h1 className="text-4xl md:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
            Media Verification
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Detect AI-generated images, videos, and voice deepfakes using advanced deep learning.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex justify-center">
          <div className="glass-card inline-flex rounded-xl p-1 gap-1">
            {(['image', 'video', 'audio'] as MediaTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => switchTab(tab)}
                className={`px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 capitalize flex items-center gap-2 ${
                  activeTab === tab
                    ? 'bg-primary text-primary-foreground shadow'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab === 'image' && <ImageIcon className="w-4 h-4" />}
                {tab === 'video' && <Video className="w-4 h-4" />}
                {tab === 'audio' && <Mic className="w-4 h-4" />}
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* Audio Coming Soon */}
        {activeTab === 'audio' && (
          <div className="glass-card p-12 text-center border border-primary/20 bg-primary/5">
            <div className="w-20 h-20 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-6">
              <Mic className="w-10 h-10 text-primary/60" />
            </div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-semibold uppercase tracking-widest mb-4">
              Coming Soon
            </div>
            <h3 className="text-2xl font-bold text-foreground mb-3">Audio Deepfake Detection</h3>
            <p className="text-muted-foreground max-w-md mx-auto leading-relaxed">
              Detect AI-generated and cloned voices with high accuracy.
              This feature is currently under development and will be available in the next release.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3 text-xs text-muted-foreground/60">
              <span className="px-3 py-1 rounded-full bg-secondary/50">Voice Clone Detection</span>
              <span className="px-3 py-1 rounded-full bg-secondary/50">AI Speech Analysis</span>
              <span className="px-3 py-1 rounded-full bg-secondary/50">Real-time Detection</span>
            </div>
          </div>
        )}

        {/* Upload Zone */}
        {activeTab !== 'audio' && <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={`
            border-2 border-dashed rounded-3xl p-10 text-center cursor-pointer
            transition-all duration-300 group hover:border-primary/50 hover:bg-white/5
            ${previewUrl ? 'border-primary/30 bg-primary/5' : 'border-border/50 bg-background/50'}
          `}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept={ACCEPT_MAP[activeTab]}
            className="hidden"
          />

          {previewUrl && selectedFile ? (
            <div className="space-y-6">
              <div className="relative w-full max-w-md mx-auto aspect-video rounded-xl overflow-hidden ring-1 ring-border shadow-2xl bg-black flex items-center justify-center">
                {selectedFile.type.startsWith("video/") ? (
                  <video src={previewUrl} controls className="w-full h-full object-contain" />
                ) : (
                  <img src={previewUrl} alt="Preview" className="w-full h-full object-cover" />
                )}
              </div>
              <p className="text-sm text-muted-foreground">Click or drag to replace media</p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center space-y-4 py-8">
              <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center group-hover:scale-110 transition-transform">
                <UploadCloud className="w-8 h-8 text-muted-foreground group-hover:text-primary transition-colors" />
              </div>
              <div className="space-y-1">
                <p className="text-xl font-medium text-foreground">
                  Drag & Drop media here
                </p>
                <p className="text-sm text-muted-foreground">or click to browse from your device</p>
              </div>
              <p className="text-xs text-muted-foreground/70 pt-4">
                {activeTab === 'image' && 'Images (JPEG, PNG, WebP — max 20MB)'}
                {activeTab === 'video' && 'Video (MP4, WEBM, MOV — max 15MB)'}
              </p>
            </div>
          )}
        </div>}

        {/* Context Form — image tab only */}
        {activeTab === 'image' && selectedFile && (
          <div className="glass-card p-6 space-y-4 border border-primary/10">
            <h3 className="text-sm font-semibold text-primary uppercase tracking-widest">Context (Optional — improves accuracy)</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground font-medium">Where did you get this?</label>
                <select
                  value={imgSource}
                  onChange={e => setImgSource(e.target.value)}
                  className="w-full bg-background/60 border border-border/50 rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
                >
                  <option value="">Select source…</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="telegram">Telegram</option>
                  <option value="instagram">Instagram</option>
                  <option value="twitter">Twitter / X</option>
                  <option value="facebook">Facebook</option>
                  <option value="youtube">YouTube</option>
                  <option value="news website">News Website</option>
                  <option value="email">Email / Forward</option>
                  <option value="i took this">I took this photo</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground font-medium">What does it claim to show?</label>
                <input
                  type="text"
                  value={imgDescription}
                  onChange={e => setImgDescription(e.target.value)}
                  placeholder="e.g. SRK at IPL 2026…"
                  className="w-full bg-background/60 border border-border/50 rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground font-medium">Why are you suspicious?</label>
                <input
                  type="text"
                  value={imgSuspicion}
                  onChange={e => setImgSuspicion(e.target.value)}
                  placeholder="e.g. face looks odd…"
                  className="w-full bg-background/60 border border-border/50 rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
              </div>
            </div>
          </div>
        )}

        {/* Action Button */}
        {activeTab !== 'audio' && selectedFile && !isAnalyzing && (
          <div className="flex justify-center">
            <button
              onClick={handleAnalyze}
              className="px-8 py-4 bg-primary text-primary-foreground font-semibold rounded-xl text-lg hover:bg-primary/90 transition-all flex items-center gap-3 shadow-[0_0_20px_hsl(0_65%_45%_/_0.3)] hover:shadow-[0_0_30px_hsl(0_65%_45%_/_0.5)] transform hover:-translate-y-1 active:translate-y-0"
            >
              Detect AI Alteration
            </button>
          </div>
        )}

        {/* Parallel loading UI — image tab only */}
        {isAnalyzing && activeTab === 'image' && (
          <div className="glass-card p-6 space-y-4 border border-primary/20 animate-fade-in">
            <p className="text-sm font-semibold text-primary uppercase tracking-widest text-center">Running Both Detectors in Parallel</p>
            <div className="space-y-3">
              {/* SightEngine */}
              <div className="flex items-center gap-4 p-3 rounded-xl bg-background/40 border border-border/30">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${seComplete ? 'bg-green-500/20' : 'bg-primary/20'}`}>
                  {seComplete
                    ? <CheckCircle className="w-5 h-5 text-green-400" />
                    : <Loader2 className="w-5 h-5 text-primary animate-spin" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground">SightEngine Pixel Analysis</p>
                  <p className="text-xs text-muted-foreground">GAN fingerprints · deepfake boundary artifacts · texture analysis</p>
                </div>
                <span className={`text-xs font-medium ${seComplete ? 'text-green-400' : 'text-primary'}`}>
                  {seComplete ? '✓ Done' : 'Running…'}
                </span>
              </div>
              {/* 6-Phase Pipeline */}
              <div className="flex items-center gap-4 p-3 rounded-xl bg-background/40 border border-border/30">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-primary/20">
                  <Loader2 className="w-5 h-5 text-primary animate-spin" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground">6-Phase Intelligent Investigation</p>
                  <p className="text-xs text-muted-foreground">Reality check · reverse search · Claude Vision forensics · trend patterns</p>
                </div>
                <span className="text-xs font-medium text-primary">Running…</span>
              </div>
            </div>
            <p className="text-xs text-center text-muted-foreground/50">This takes 15–30s — Claude Vision is analysing every pixel and searching the web</p>
          </div>
        )}

        {/* Video loading */}
        {isAnalyzing && activeTab === 'video' && (
          <div className="flex justify-center">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
              <span>Extracting frames &amp; analysing…</span>
            </div>
          </div>
        )}

        {/* Results Section */}
        {result && activeTab !== 'audio' && (
          <div className="animate-fade-up space-y-5">

            {/* ── Verdict Card ─────────────────────────────────────────── */}
            <div className={`p-7 rounded-3xl border backdrop-blur-sm ${bgColor} transition-all duration-500`}>
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    {isUnavailable ? <Info className="w-8 h-8 text-muted-foreground" />
                      : isAi      ? <AlertTriangle className={`w-8 h-8 ${verdictColor}`} />
                      : isUncertain ? <Info className={`w-8 h-8 ${verdictColor}`} />
                      : <CheckCircle className={`w-8 h-8 ${verdictColor}`} />}
                    <h2 className={`text-3xl font-bold ${verdictColor}`}>
                      {isUnavailable ? 'Service Unavailable' : verdictDisplay}
                    </h2>
                  </div>
                  <p className="text-muted-foreground text-sm">
                    {result.filename}
                    {isIntelligent && result.confidence && ` · Confidence: ${result.confidence} (${result.confidence_pct}%)`}
                    {'frames_analyzed' in result && ` · ${(result as {frames_analyzed:number}).frames_analyzed} frames`}
                  </p>
                </div>
                {!isUnavailable && (
                  <div className="w-full md:w-56 space-y-2 bg-background/40 p-4 rounded-2xl ring-1 ring-border">
                    <div className="flex justify-between items-end">
                      <span className="text-xs text-muted-foreground">AI Probability</span>
                      <span className={`text-2xl font-bold ${verdictColor}`}>{result.ai_probability}%</span>
                    </div>
                    <div className="h-2 bg-secondary rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${
                          result.ai_probability >= 60 ? 'bg-red-500'
                          : result.ai_probability >= 40 ? 'bg-yellow-500'
                          : 'bg-green-500'
                        }`}
                        style={{width: `${result.ai_probability}%`}}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground/60 text-right">
                      {result.ai_probability >= 60 ? 'Likely AI-generated' : result.ai_probability >= 40 ? 'Uncertain' : 'Likely genuine'}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* ── Two-detector breakdown (image intelligent only) ────── */}
            {isIntelligent && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                {/* SightEngine card */}
                {(() => {
                  const se = result.sightengine;
                  const seAvail = se?.available;
                  const seScore = se?.score ?? 0;
                  const borderCls = seAvail
                    ? seScore >= 60 ? 'border-red-500/20' : seScore >= 40 ? 'border-yellow-500/20' : 'border-green-500/20'
                    : 'border-border/30';
                  return (
                    <div className={`glass-card p-5 space-y-4 border ${borderCls}`}>
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-bold text-foreground">SightEngine</p>
                          <p className="text-xs text-muted-foreground">Pixel-level AI detector</p>
                        </div>
                        <div className="text-right">
                          {seAvail ? (
                            <>
                              <p className={`text-2xl font-bold ${seScore >= 60 ? 'text-red-400' : seScore >= 40 ? 'text-yellow-400' : 'text-green-400'}`}>
                                {seScore}%
                              </p>
                              <p className="text-xs text-muted-foreground">AI probability</p>
                            </>
                          ) : (
                            <>
                              <p className="text-2xl font-bold text-muted-foreground">N/A</p>
                              <p className="text-xs text-muted-foreground">Not configured</p>
                            </>
                          )}
                        </div>
                      </div>
                      {seAvail ? (
                        <>
                          <div className="space-y-2">
                            <div className="flex justify-between text-xs text-muted-foreground">
                              <span>AI Generated</span><span className="font-medium text-foreground">{se.ai_generated}%</span>
                            </div>
                            <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                              <div className="h-full bg-orange-400 rounded-full" style={{width:`${se.ai_generated}%`}} />
                            </div>
                            <div className="flex justify-between text-xs text-muted-foreground">
                              <span>Deepfake</span><span className="font-medium text-foreground">{se.deepfake}%</span>
                            </div>
                            <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                              <div className="h-full bg-purple-400 rounded-full" style={{width:`${se.deepfake}%`}} />
                            </div>
                          </div>
                          <div className="pt-2 border-t border-border/30">
                            <p className="text-xs text-muted-foreground">
                              Weight in final: <span className="font-semibold text-foreground">{se.weight_used}%</span>
                              <span className="ml-2 text-muted-foreground/60">· {se.conflict?.replace(/_/g,' ').toLowerCase()}</span>
                            </p>
                          </div>
                        </>
                      ) : (
                        <div className="pt-2 border-t border-border/30 space-y-1">
                          <p className="text-xs text-muted-foreground/70">
                            SightEngine API credentials not set — running pipeline-only mode.
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Weight in final: <span className="font-semibold text-foreground">0%</span>
                            <span className="ml-2 text-muted-foreground/60">· pipeline carries 100%</span>
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* 6-Phase Pipeline card */}
                {(() => {
                  // pipeline_score may be missing if backend restart needed — fall back to final_score
                  const pipeScore = result.verdict_engine?.pipeline_score ?? result.ai_probability ?? 0;
                  const pipeWeight = 100 - (result.sightengine?.weight_used ?? 0);
                  const imgType = result.phase_details?.phase4_pixel?.image_type;
                  const showImgType = imgType && imgType !== 'UNKNOWN';
                  const peopleCount = result.phase_details?.phase4_pixel?.people_count ?? 0;
                  const contactZones = result.phase_details?.phase4_pixel?.contact_zones ?? 0;
                  return (
                    <div className="glass-card p-5 space-y-4 border border-primary/20">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-bold text-foreground">6-Phase Pipeline</p>
                          <p className="text-xs text-muted-foreground">Reality + forensics investigation</p>
                        </div>
                        <div className="text-right">
                          <p className={`text-2xl font-bold ${pipeScore >= 60 ? 'text-red-400' : pipeScore >= 40 ? 'text-yellow-400' : 'text-green-400'}`}>
                            {pipeScore}%
                          </p>
                          <p className="text-xs text-muted-foreground">AI probability</p>
                        </div>
                      </div>
                      <div className="space-y-2">
                        {[
                          { label: 'P1 Context',  val: result.verdict_engine?.phase_scores?.context ?? 0 },
                          { label: 'P2 Reality',  val: result.verdict_engine?.phase_scores?.reality ?? 0 },
                          { label: 'P3 Search',   val: result.verdict_engine?.phase_scores?.search  ?? 0 },
                          { label: 'P4 Pixels',   val: result.verdict_engine?.phase_scores?.pixel   ?? 0 },
                          { label: 'P6 Trend',    val: result.verdict_engine?.phase_scores?.trend    ?? 0 },
                        ].map(({label, val}) => (
                          <div key={label} className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground w-20 flex-shrink-0">{label}</span>
                            <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                              <div className={`h-full rounded-full transition-all duration-700 ${val >= 60 ? 'bg-red-400' : val >= 40 ? 'bg-yellow-400' : 'bg-green-400'}`} style={{width:`${val}%`}} />
                            </div>
                            <span className="text-xs text-foreground font-medium w-8 text-right">{val}%</span>
                          </div>
                        ))}
                      </div>
                      <div className="pt-2 border-t border-border/30">
                        <p className="text-xs text-muted-foreground">
                          Weight in final: <span className="font-semibold text-foreground">{pipeWeight}%</span>
                          {showImgType && (
                            <span className="ml-2 text-muted-foreground/60">
                              · {imgType}
                              {peopleCount > 0 && ` · ${peopleCount} people · ${contactZones} contact zones`}
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}

            {/* ── Conflict alert ─────────────────────────────────────── */}
            {isIntelligent && result.verdict_engine?.conflicts?.length > 0 && (
              <div className="p-4 rounded-2xl bg-yellow-500/10 border border-yellow-500/20 text-sm text-yellow-300 flex items-start gap-3">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span><span className="font-semibold">Conflict resolved: </span>{result.verdict_engine.conflicts[0]}</span>
              </div>
            )}

            {/* ── Explanation ────────────────────────────────────────── */}
            {result.explanation && (
              <div className="glass-card p-6 space-y-4">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                    <ImageIcon className="w-5 h-5 text-primary" />
                    Analysis Summary
                  </h3>
                  <LanguageSelector selected={language} onChange={setLanguage} />
                </div>
                <p className="text-foreground leading-relaxed">{getExplanation()}</p>
              </div>
            )}

            {/* ── Full Phase Breakdown (intelligent) ─────────────────── */}
            {isIntelligent && (
              <details className="group border border-border/50 rounded-2xl overflow-hidden bg-background/50 backdrop-blur-sm">
                <summary className="px-6 py-4 cursor-pointer font-medium text-foreground flex items-center gap-3 select-none hover:bg-white/5 transition-colors">
                  <ChevronDown className="w-5 h-5 text-primary group-open:rotate-180 transition-transform" />
                  Full Phase Breakdown
                </summary>
                <div className="px-6 pb-6 pt-4 border-t border-border/50 bg-black/20 space-y-3">
                  {[
                    { label: 'Phase 1 — Context Intelligence',        key: 'phase1_context', ai: true  },
                    { label: 'Phase 2 — Reality Verification',        key: 'phase2_reality', ai: false },
                    { label: 'Phase 3 — Reverse Image Search',        key: 'phase3_search',  ai: false },
                    { label: 'Phase 4 — Pixel Forensics (Claude Vision)', key: 'phase4_pixel', ai: true },
                    { label: 'Phase 6 — Trend & Viral Pattern',       key: 'phase6_trend',   ai: true  },
                  ].map(({ label, key, ai }) => {
                    const phase = result.phase_details[key];
                    const score = phase?.score ?? 0;
                    const flagged = ai ? score >= 60 : score <= 40;
                    const barColor = flagged ? 'bg-red-500' : score >= 40 && score <= 60 ? 'bg-yellow-500' : 'bg-green-500';
                    return (
                      <div key={key} className="space-y-1">
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-foreground font-medium">{label}</span>
                          <span className="text-muted-foreground text-xs">{score}/100</span>
                        </div>
                        <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                          <div className={`h-full ${barColor} rounded-full transition-all duration-700`} style={{width:`${score}%`}} />
                        </div>
                        {phase?.reasoning?.[0] && <p className="text-xs text-muted-foreground/70">{phase.reasoning[0]}</p>}
                        {key === 'phase4_pixel' && phase?.key_evidence && (
                          <p className="text-xs text-primary/80 font-medium">Key finding: {phase.key_evidence}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </details>
            )}

            {/* ── Raw data (video / non-intelligent) ─────────────────── */}
            {!isIntelligent && result?.raw && (
              <details className="group border border-border/50 rounded-2xl overflow-hidden bg-background/50 backdrop-blur-sm">
                <summary className="px-6 py-4 cursor-pointer font-medium text-foreground flex items-center gap-3 select-none hover:bg-white/5 transition-colors">
                  <Info className="w-5 h-5 text-primary" />
                  Raw Model Data
                </summary>
                <div className="px-6 pb-6 pt-2 text-sm text-muted-foreground font-mono space-y-2 border-t border-border/50 bg-black/20">
                  {result.raw.map((item: {label:string; score:number}, i:number) => (
                    <div key={i} className="flex justify-between">
                      <span>{item.label}</span><span>{item.score.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default MediaVerification;
