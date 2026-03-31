import { useState, useRef } from "react";
import { UploadCloud, Image as ImageIcon, Video, Mic, AlertTriangle, CheckCircle, Loader2, Info } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";
import LanguageSelector from "@/components/LanguageSelector";
import { detectImage, detectVideo, detectAudio, DetectImageResponse } from "@/services/api";

type MediaTab = 'image' | 'video' | 'audio';

const MediaVerification = () => {
  const [activeTab, setActiveTab] = useState<MediaTab>('image');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<DetectImageResponse | null>(null);
  const [language, setLanguage] = useState<'en' | 'hi' | 'mr'>('en');

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

  const handleAnalyze = async () => {
    if (!selectedFile) return;
    setIsAnalyzing(true);
    setResult(null);
    try {
      let response: DetectImageResponse;
      if (activeTab === 'audio') {
        response = await detectAudio(selectedFile);
      } else if (activeTab === 'video') {
        response = await detectVideo(selectedFile);
      } else {
        response = await detectImage(selectedFile);
      }
      setResult(response);
      toast({ title: "Analysis Complete", description: `${activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} verification finished.` });
    } catch (error: any) {
      toast({ title: "Analysis Failed", description: error.message || "Failed to analyze media.", variant: "destructive" });
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

  // Determine UI colors based on verdict (covers image/video AND audio verdicts)
  const isUnavailable = result?.status === "unavailable";
  const isAi = result?.verdict === "likely AI-generated" || result?.verdict === "likely AI-generated voice";
  const isUncertain = result?.verdict === "uncertain";

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
          <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-primary/20 ring-1 ring-primary/30 mb-4 shadow-[0_0_30px_rgba(var(--primary),0.3)]">
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

          {activeTab === 'audio' && selectedFile ? (
            <div className="flex flex-col items-center space-y-3 py-6">
              <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center">
                <Mic className="w-8 h-8 text-primary" />
              </div>
              <p className="text-foreground font-medium">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground">Click or drag to replace</p>
            </div>
          ) : previewUrl && selectedFile ? (
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
                {activeTab === 'audio' ? (
                  <Mic className="w-8 h-8 text-muted-foreground group-hover:text-primary transition-colors" />
                ) : (
                  <UploadCloud className="w-8 h-8 text-muted-foreground group-hover:text-primary transition-colors" />
                )}
              </div>
              <div className="space-y-1">
                <p className="text-xl font-medium text-foreground">
                  {activeTab === 'audio' ? 'Drop audio file here' : 'Drag & Drop media here'}
                </p>
                <p className="text-sm text-muted-foreground">or click to browse from your device</p>
              </div>
              <p className="text-xs text-muted-foreground/70 pt-4">
                {activeTab === 'image' && 'Images (JPEG, PNG, WebP — max 20MB)'}
                {activeTab === 'video' && 'Video (MP4, WEBM, MOV — max 15MB)'}
                {activeTab === 'audio' && 'Audio (MP3, WAV, OGG, WEBM — max 10MB)'}
              </p>
            </div>
          )}
        </div>}

        {/* Action Button */}
        {activeTab !== 'audio' && selectedFile && (
          <div className="flex justify-center">
            <button
              onClick={handleAnalyze}
              disabled={isAnalyzing}
              className="px-8 py-4 bg-primary text-primary-foreground font-semibold rounded-xl text-lg hover:bg-primary/90 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-3 shadow-[0_0_20px_rgba(var(--primary),0.3)] hover:shadow-[0_0_30px_rgba(var(--primary),0.5)] transform hover:-translate-y-1 active:translate-y-0"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {activeTab === 'video' ? 'Extracting Frames & Analyzing…' : activeTab === 'audio' ? 'Analyzing Audio…' : 'Analyzing Image…'}
                </>
              ) : (
                <>Detect AI {activeTab === 'audio' ? 'Voice' : 'Alteration'}</>
              )}
            </button>
          </div>
        )}

        {/* Results Section */}
        {result && activeTab !== 'audio' && (
          <div className="animate-fade-up space-y-6">
            <div className={`p-8 rounded-3xl border backdrop-blur-sm ${bgColor} transition-all duration-500`}>
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">

                {/* Verdict */}
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    {isUnavailable ? (
                      <Info className="w-8 h-8 text-muted-foreground" />
                    ) : isAi ? (
                      <AlertTriangle className={`w-8 h-8 ${verdictColor}`} />
                    ) : isUncertain ? (
                      <Info className={`w-8 h-8 ${verdictColor}`} />
                    ) : (
                      <CheckCircle className={`w-8 h-8 ${verdictColor}`} />
                    )}
                    <h2 className={`text-3xl font-bold capitalize ${verdictColor}`}>
                      {isUnavailable ? "Service Unavailable" : result.verdict}
                    </h2>
                  </div>
                  <p className="text-muted-foreground">
                    Based on analyzing {result.filename}
                    {(result as any).frames_analyzed && ` (${(result as any).frames_analyzed} frames processed)`}
                  </p>
                </div>

                {/* Probability Score */}
                {!isUnavailable && (
                  <div className="w-full md:w-64 space-y-3 bg-background/40 p-5 rounded-2xl ring-1 ring-border">
                    <div className="flex justify-between items-end">
                      <span className="text-sm font-medium text-muted-foreground">AI Probability</span>
                      <span className={`text-2xl font-bold ${verdictColor}`}>{result.ai_probability}%</span>
                    </div>
                    <Progress value={result.ai_probability} className="h-2" />
                  </div>
                )}
              </div>

              {/* Multilingual Explanation */}
              {result.explanation && (
                <div className="mt-8 pt-6 border-t border-border/20 space-y-4">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
                      <ImageIcon className="w-5 h-5 text-primary" />
                      Analysis Summary
                    </h3>
                    <LanguageSelector selected={language} onChange={setLanguage} />
                  </div>
                  <div className="bg-background/40 p-5 rounded-2xl ring-1 ring-border">
                    <p className="text-lg text-foreground leading-relaxed">
                      {getExplanation()}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Raw Analysis Logs */}
            <details className="group border border-border/50 rounded-2xl overflow-hidden bg-background/50 backdrop-blur-sm">
              <summary className="px-6 py-4 cursor-pointer font-medium text-foreground flex items-center gap-3 select-none hover:bg-white/5 transition-colors">
                <Info className="w-5 h-5 text-primary" />
                View Raw Model Data
              </summary>
              <div className="px-6 pb-6 pt-2 text-sm text-muted-foreground font-mono space-y-2 border-t border-border/50 bg-black/20">
                {result.raw.map((item, i) => (
                  <div key={i} className="flex justify-between">
                    <span>{item.label}</span>
                    <span>{item.score.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  );
};

export default MediaVerification;
