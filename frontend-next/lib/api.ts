const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type TaskStatus = "queued" | "running" | "succeeded" | "failed" | "expired" | "cancelled";

export interface Task {
  id: string;
  status: TaskStatus;
  model: string;
  ratio_requested: string;
  resolution_requested: string;
  duration_requested: number | null;
  generate_audio: boolean;
  watermark: boolean;
  seed_requested: number | null;
  content_items: ContentItem[];
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  video_url: string | null;
  last_frame_url: string | null;
  duration_actual: number | null;
  ratio_actual: string | null;
  resolution_actual: string | null;
  seed_actual: number | null;
  framespersecond: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  error_code: string | null;
  error_message: string | null;
  upscale_resolution: string | null;
}

export interface ContentItem {
  type: "text" | "image_url" | "video_url" | "audio_url";
  text?: string;
  image_url?: { url: string };
  video_url?: { url: string };
  audio_url?: { url: string };
  role?: string; // first_frame | last_frame | reference_image | reference_video | reference_audio
}

export interface GenerationRequest {
  content: ContentItem[];
  ratio: string;
  resolution: string;
  duration?: number;
  generate_audio: boolean;
  seed?: number;
  upscale_resolution?: string;
}

export async function submitTask(req: GenerationRequest): Promise<Task> {
  const res = await fetch(`${API_BASE}/generations/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getTask(id: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/generations/tasks/${id}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export function toDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
