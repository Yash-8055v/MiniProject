import { useState, useRef } from "react";
import { UploadCloud, Image as ImageIcon, Video, AlertTriangle, CheckCircle, Loader2, Info } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";
import LanguageSelector from "@/components/LanguageSelector";
import { detectImage, detectVideo, DetectImageResponse } from "@/services/api";

const MediaVerification = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<DetectImageResponse | null>(null);
  const [language, setLanguage] = useState<'en' | 'hi' | 'mr'>('en');
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5MB
  const MAX_VIDEO_SIZE = 15 * 1024 * 1024; // 15MB

  const handleValidFile = (file: File) => {
    const isVideo = file.type.startsWith("video/");
    const limit = isVideo ? MAX_VIDEO_SIZE : MAX_IMAGE_SIZE;
    
    if (file.size > limit) {
      toast({
        title: "File too large",
        description: `Max ${isVideo ? "15MB" : "5MB"} allowed for ${isVideo ? "videos" : "images"}.`,
        variant: "destructive",
      });
      return;
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setResult(null); // Reset previous result
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/") && !file.type.startsWith("video/")) {
        toast({
          title: "Invalid file type",
          description: "Please upload an image or video file.",
          variant: "destructive",
        });
        return;
      }
      handleValidFile(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && (file.type.startsWith("image/") || file.type.startsWith("video/"))) {
      handleValidFile(file);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;

    setIsAnalyzing(true);
    setResult(null);

    const isVideo = selectedFile.type.startsWith("video/");

    try {
      const response = isVideo ? await detectVideo(selectedFile) : await detectImage(selectedFile);
      setResult(response);
      toast({
        title: "Analysis Complete",
        description: `${isVideo ? "Video" : "Image"} verification finished successfully.`,
      });
    } catch (error: any) {
      toast({
        title: "Analysis Failed",
        description: error.message || "Failed to analyze the media.",
        variant: "destructive",
      });
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

  // Determine UI colors based on verdict
  const isAi = result?.verdict === "likely AI-generated";
  const isUncertain = result?.verdict === "uncertain";
  
  const verdictColor = isAi 
    ? "text-red-500" 
    : isUncertain 
      ? "text-orange-500" 
      : "text-green-500";
      
  const bgColor = isAi 
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
            <Video className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-4xl md:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
            Media Verification
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Upload an image or video to detect if it's AI-generated or authentic using our 
            advanced deep learning detector.
          </p>
        </div>

        {/* Upload Zone */}
        <div 
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
            accept="image/*,video/*" 
            className="hidden" 
          />
          
          {previewUrl && selectedFile ? (
            <div className="space-y-6">
              <div className="relative w-full max-w-md mx-auto aspect-video rounded-xl overflow-hidden ring-1 ring-border shadow-2xl bg-black flex items-center justify-center">
                {selectedFile.type.startsWith("video/") ? (
                  <video 
                    src={previewUrl} 
                    controls 
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <img 
                    src={previewUrl} 
                    alt="Preview" 
                    className="w-full h-full object-cover"
                  />
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
                <p className="text-sm text-muted-foreground">
                  or click to browse from your device
                </p>
              </div>
              <p className="text-xs text-muted-foreground/70 pt-4">
                Supports Images (JPEG, PNG, WebP - max 5MB) and Video (MP4, WEBM, MOV - max 15MB)
              </p>
            </div>
          )}
        </div>

        {/* Action Button */}
        {selectedFile && (
          <div className="flex justify-center">
            <button
              onClick={handleAnalyze}
              disabled={isAnalyzing}
              className="px-8 py-4 bg-primary text-primary-foreground font-semibold rounded-xl text-lg hover:bg-primary/90 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-3 shadow-[0_0_20px_rgba(var(--primary),0.3)] hover:shadow-[0_0_30px_rgba(var(--primary),0.5)] transform hover:-translate-y-1 active:translate-y-0"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {selectedFile.type.startsWith("video/") ? "Extracting Frames & Analyzing..." : "Analyzing Image..."}
                </>
              ) : (
                <>Detect AI Alteration</>
              )}
            </button>
          </div>
        )}

        {/* Results Section */}
        {result && (
          <div className="animate-fade-up space-y-6">
            <div className={`p-8 rounded-3xl border backdrop-blur-sm ${bgColor} transition-all duration-500`}>
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                
                {/* Verdict */}
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    {isAi ? (
                      <AlertTriangle className={`w-8 h-8 ${verdictColor}`} />
                    ) : isUncertain ? (
                      <Info className={`w-8 h-8 ${verdictColor}`} />
                    ) : (
                      <CheckCircle className={`w-8 h-8 ${verdictColor}`} />
                    )}
                    <h2 className={`text-3xl font-bold capitalize ${verdictColor}`}>
                      {result.verdict}
                    </h2>
                  </div>
                  <p className="text-muted-foreground">
                    Based on analyzing {result.filename}
                    {(result as any).frames_analyzed && ` (${(result as any).frames_analyzed} frames processed)`}
                  </p>
                </div>

                {/* Probability Score */}
                <div className="w-full md:w-64 space-y-3 bg-background/40 p-5 rounded-2xl ring-1 ring-border">
                  <div className="flex justify-between items-end">
                    <span className="text-sm font-medium text-muted-foreground">AI Probability</span>
                    <span className={`text-2xl font-bold ${verdictColor}`}>{result.ai_probability}%</span>
                  </div>
                  <Progress value={result.ai_probability} className="h-2" />
                </div>
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
