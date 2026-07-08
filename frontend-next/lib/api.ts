const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type TaskStatus = "queued" | "running" | "succeeded" | "failed" | "expired" | "cancelled";

export interface ImageTask {
  id: string;
  status: "succeeded" | "failed";
  model: string;
  prompt: string;
  size_requested: string | null;
  watermark: boolean;
  seed_requested: number | null;
  created_at: string;
  updated_at: string;
  image_url: string | null;
  image_size: string | null;
  output_tokens: number | null;
  total_tokens: number | null;
  error_code: string | null;
  error_message: string | null;
}

export interface ImageGenerationRequest {
  prompt: string;
  image?: string | string[];
  size?: string;
  output_format?: string;
  seed?: number;
}

export async function getImageTask(id: string): Promise<ImageTask> {
  const res = await fetch(`${API_BASE}/images/tasks/${id}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function listImageTasks(): Promise<ImageTask[]> {
  const res = await fetch(`${API_BASE}/images/tasks`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function submitImageTask(req: ImageGenerationRequest): Promise<ImageTask> {
  const res = await fetch(`${API_BASE}/images/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const text = await res.text();
    try {
      const json = JSON.parse(text);
      const msg = json?.detail || json?.error?.message || json?.message;
      if (msg) throw new Error(msg);
    } catch (e) {
      if (e instanceof SyntaxError === false) throw e;
    }
    throw new Error(`Error ${res.status}: ${text}`);
  }
  return res.json();
}

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
  name: string | null;
  batch_id: string | null;
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
  model?: string;
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
    try {
      const json = JSON.parse(text);
      const msg = json?.detail || json?.error?.message || json?.message;
      if (msg) throw new Error(msg);
    } catch (e) {
      if (e instanceof SyntaxError === false) throw e;
    }
    throw new Error(`Error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getTask(id: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/generations/tasks/${id}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function listTasks(): Promise<Task[]> {
  const res = await fetch(`${API_BASE}/generations/tasks`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function listBatchTasks(batchId: string): Promise<Task[]> {
  const res = await fetch(`${API_BASE}/generations/tasks?batch_id=${encodeURIComponent(batchId)}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface BatchSummary {
  batch_id: string;
  name: string;
  total: number;
  done: number;
  failed: number;
  created_at: string | null;
  model: string | null;
  resolution: string | null;
  upscale_resolution: string | null;
}

export async function listBatches(): Promise<BatchSummary[]> {
  const res = await fetch(`${API_BASE}/generations/batches`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface EnhanceStats {
  by_resolution: { resolution: string; count: number; total_credits: number }[];
  total_count: number;
  total_credits: number;
}

export async function getEnhanceStats(): Promise<EnhanceStats> {
  const res = await fetch(`${API_BASE}/generations/enhance/stats`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function retryBatchFailed(batchId: string): Promise<{ retried: number }> {
  const res = await fetch(`${API_BASE}/generations/batches/${encodeURIComponent(batchId)}/retry-failed`, { method: "POST" });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface BatchTask {
  id: string;
  name: string;
  status: TaskStatus;
  error_code: string | null;
  error_message: string | null;
}

export async function submitBatch(
  file: File,
  params: {
    model: string;
    ratio: string;
    resolution: string;
    duration: number;
    generate_audio: boolean;
    upscale_resolution?: string;
  }
): Promise<BatchTask[]> {
  const form = new FormData();
  form.append("file", file);
  form.append("model", params.model);
  form.append("ratio", params.ratio);
  form.append("resolution", params.resolution);
  form.append("duration", String(params.duration));
  form.append("generate_audio", String(params.generate_audio).toLowerCase());
  if (params.upscale_resolution) form.append("upscale_resolution", params.upscale_resolution);

  const res = await fetch(`${API_BASE}/generations/batch`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    try {
      const json = JSON.parse(text);
      const msg = json?.detail || json?.error?.message || json?.message;
      if (msg) throw new Error(msg);
    } catch (e) {
      if (e instanceof SyntaxError === false) throw e;
    }
    throw new Error(`Error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function cancelTasksBulk(taskIds: string[]): Promise<{ cancelled: number; skipped: number }> {
  const res = await fetch(`${API_BASE}/generations/tasks/cancel-bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_ids: taskIds }),
  });
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

export async function uploadFile(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/uploads`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed ${res.status}: ${text}`);
  }
  const { url } = await res.json();
  return url;
}
