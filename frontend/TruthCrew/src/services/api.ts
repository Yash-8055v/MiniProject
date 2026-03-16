const API_URL = import.meta.env.VITE_API_URL || "https://truthcrew-api-miniproject.onrender.com";

export interface Source {
  title: string;
  url: string;
  source: string;
  trusted: boolean;
}

export interface VerifyResponse {
  verdict: string;
  confidence: number;
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
