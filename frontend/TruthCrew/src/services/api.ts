const API_URL = import.meta.env.VITE_API_URL || "https://truthcrew-api-miniproject.onrender.com";

export interface Source {
  title: string;
  url: string;
  source: string;
  trusted: boolean;
}

export interface CredibilityLayer {
  score: number;
  weight: number;
}

export interface CredibilityLayers {
  source_tier: CredibilityLayer;
  source_count: CredibilityLayer;
  evidence_alignment: CredibilityLayer;
  claim_verifiability: CredibilityLayer;
  cross_agreement: CredibilityLayer;
}

export interface VerifyResponse {
  verdict: string;
  confidence: number;
  credibility_layers?: CredibilityLayers;
  english: string;
  hindi: string;
  marathi: string;
  sources?: Source[];
}

interface ApiResponse {
  status: string;
  languages: string[];
  data: VerifyResponse;
}

export async function verifyNews(text: string): Promise<VerifyResponse> {
  const formData = new FormData();
  formData.append("text", text);

  const response = await fetch(`${API_URL}/verify`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const message = errorData?.detail || `Server error (${response.status})`;
    throw new Error(message);
  }

  const json: ApiResponse = await response.json();

  if (json.status !== "success" || !json.data) {
    throw new Error("Unexpected response from server");
  }

  return json.data;
}

export async function fetchHeatmap(query: string): Promise<Record<string, number>> {
  const url = new URL(`${API_URL}/api/heatmap`);
  url.searchParams.append("query", query);

  const response = await fetch(url.toString());

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const message = errorData?.detail || `Server error (${response.status})`;
    throw new Error(message);
  }

  const json = await response.json();
  if (json.status !== "success" || !json.data) {
    throw new Error("Unexpected response from server");
  }

  return json.data;
}

export async function fetchHeatmapInsight(
  query: string,
  heatmapData: Record<string, number>
): Promise<string> {
  const response = await fetch(`${API_URL}/api/heatmap-insight`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, heatmap_data: heatmapData }),
  });

  if (!response.ok) {
    throw new Error(`Insight API error (${response.status})`);
  }

  const json = await response.json();
  return json.insight || "";
}

export interface DetectImageResponse {
  status: string;
  ai_probability: number;
  verdict: string;
  filename: string;
  raw: { label: string; score: number }[];
  explanation: {
    english: string;
    hindi: string;
    marathi: string;
  };
}

export async function detectImage(image: File): Promise<DetectImageResponse> {
  const formData = new FormData();
  formData.append("image", image);

  const response = await fetch(`${API_URL}/api/detect-image`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const message = errorData?.detail || `Server error (${response.status})`;
    throw new Error(message);
  }

  const json = await response.json();
  if (json.status !== "success") {
    throw new Error("Unexpected response from server");
  }

  return json;
}

export async function transcribeAudio(audioBlob: Blob, filename = 'audio.webm'): Promise<string> {
  const formData = new FormData();
  formData.append('audio', audioBlob, filename);

  const response = await fetch(`${API_URL}/api/agents/stt`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || `STT error (${response.status})`);
  }

  const json = await response.json();
  return json.transcript as string;
}

export async function speakText(text: string, language: string): Promise<Blob> {
  const response = await fetch(`${API_URL}/api/agents/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || `TTS error (${response.status})`);
  }

  return response.blob();
}

export async function detectAudio(audio: File): Promise<DetectImageResponse> {
  const formData = new FormData();
  formData.append('audio', audio);

  const response = await fetch(`${API_URL}/api/detect-audio`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const message = errorData?.detail || `Server error (${response.status})`;
    throw new Error(message);
  }

  const json = await response.json();
  if (json.status !== 'success') {
    throw new Error('Unexpected response from server');
  }

  return json;
}

export async function detectVideo(video: File): Promise<DetectImageResponse> {
  const formData = new FormData();
  formData.append("video", video);

  const response = await fetch(`${API_URL}/api/detect-video`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const message = errorData?.detail || `Server error (${response.status})`;
    throw new Error(message);
  }

  const json = await response.json();
  if (json.status !== "success") {
    throw new Error("Unexpected response from server");
  }

  return json;
}
