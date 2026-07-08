"use client";

import { useEffect, useRef, useState } from "react";
import { Task, getTask, ContentItem, upscaleTask } from "@/lib/api";

interface Props {
  task: Task;
  onUpdate: (t: Task) => void;
}

const POLL_INTERVAL = 3000;

function getPrompt(items: ContentItem[]): string {
  return items.find((i) => i.type === "text")?.text ?? "";
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

function VideoThumbnail({ src }: { src: string }) {
  const [thumbnail, setThumbnail] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const proxySrc = `${API_BASE}/generations/proxy?url=${encodeURIComponent(src)}`;
    const video = document.createElement("video");
    video.crossOrigin = "anonymous";
    video.muted = true;
    video.preload = "metadata";
    video.src = proxySrc;

    const capture = () => {
      video.currentTime = 0.01;
    };

    const draw = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth || 320;
        canvas.height = video.videoHeight || 180;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          setThumbnail(canvas.toDataURL("image/jpeg", 0.8));
        }
      } catch {
        // CORS blocked — leave thumbnail null, show grey
      }
      video.src = "";
    };

    video.addEventListener("loadedmetadata", capture);
    video.addEventListener("seeked", draw);
    video.load();

    return () => {
      video.removeEventListener("loadedmetadata", capture);
      video.removeEventListener("seeked", draw);
      video.src = "";
    };
  }, [src]);

  if (playing) {
    return (
      <video
        ref={videoRef}
        src={src}
        controls
        autoPlay
        className="w-full h-full object-cover"
      />
    );
  }

  return (
    <button onClick={() => setPlaying(true)} className="absolute inset-0 w-full h-full group">
      {thumbnail ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={thumbnail} alt="" className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full bg-zinc-800" />
      )}
      <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="w-12 h-12 rounded-full bg-black/60 flex items-center justify-center">
          <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5 ml-0.5">
            <path d="M8 5v14l11-7z" />
          </svg>
        </div>
      </div>
    </button>
  );
}

export default function TaskCard({ task: initial, onUpdate }: Props) {
  const [task, setTask] = useState(initial);
  const [upscalePickerOpen, setUpscalePickerOpen] = useState(false);
  const [upscaling, setUpscaling] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setTask(initial);
  }, [initial]);

  // Polling: stop for terminal statuses, but keep going if we're waiting for upscale to complete
  const waitingForUpscale = upscaling && !task.upscale_done;
  const shouldStop =
    (task.status === "succeeded" || task.status === "failed" || task.status === "expired") &&
    !waitingForUpscale;

  useEffect(() => {
    if (shouldStop) return;

    timerRef.current = setTimeout(async () => {
      try {
        const updated = await getTask(task.id);
        setTask(updated);
        onUpdate(updated);
        // If upscale just completed, stop polling
        if (upscaling && updated.upscale_done) setUpscaling(false);
      } catch {/* ignore */}
    }, POLL_INTERVAL);

    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [task, shouldStop, upscaling]);

  async function handleUpscale(resolution: string) {
    setUpscalePickerOpen(false);
    setUpscaling(true);
    try {
      await upscaleTask(task.id, resolution);
      // Update local state optimistically so upscale_resolution shows immediately
      setTask((t) => ({ ...t, upscale_resolution: resolution }));
    } catch {
      setUpscaling(false);
    }
  }

  const videoAlive = task.video_url && task.updated_at
    ? Date.now() - new Date(task.updated_at).getTime() < 23.5 * 60 * 60 * 1000
    : false;

  const prompt = getPrompt(task.content_items);
  const promptShort = prompt.length > 100 ? prompt.slice(0, 100) + "…" : prompt;

  const res = task.resolution_actual ?? task.resolution_requested;
  const ratio = task.ratio_actual ?? task.ratio_requested;
  const dur = task.duration_actual ?? task.duration_requested;
  const upscale = task.upscale_done ? task.upscale_resolution : null;

  const meta = [res, ratio, dur ? `${dur}s` : null, upscale ? `→${upscale}` : null]
    .filter(Boolean)
    .join(" · ");

  const showUpscaleBtn = task.status === "succeeded" && videoAlive && !task.upscale_done && !upscaling;

  return (
    <div className="rounded-xl overflow-hidden bg-white/5 border border-white/8 flex flex-col">
      <div className="relative aspect-video bg-zinc-900 flex items-center justify-center">
        {task.status === "succeeded" && videoAlive ? (
          <div className="absolute inset-0 group">
            <VideoThumbnail src={task.video_url!} />

            {/* Upscale shimmer overlay */}
            {waitingForUpscale && (
              <div className="absolute inset-0 z-10 pointer-events-none">
                <div className="absolute inset-0 bg-black/50" />
                <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/8 to-white/0 animate-shimmer bg-[length:200%_100%]" />
                <div className="absolute bottom-3 left-3 flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-white/50 animate-pulse" />
                  <span className="text-white/50 text-xs">Upscaling...</span>
                </div>
              </div>
            )}

            {/* Action buttons (open, download, upscale) */}
            <div className="absolute top-2 right-2 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity z-20">
              {showUpscaleBtn && !upscalePickerOpen && (
                <button
                  onClick={(e) => { e.stopPropagation(); setUpscalePickerOpen(true); }}
                  className="w-8 h-8 rounded-full bg-black/60 flex items-center justify-center hover:bg-black/80 transition-colors"
                  title="Upscale (Topaz)"
                >
                  {/* Arrow up icon */}
                  <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" className="w-3.5 h-3.5">
                    <path d="M12 19V5M5 12l7-7 7 7" />
                  </svg>
                </button>
              )}
              <a
                href={task.video_url!}
                target="_blank"
                rel="noopener noreferrer"
                className="w-8 h-8 rounded-full bg-black/60 flex items-center justify-center hover:bg-black/80 transition-colors"
                title="Open"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" className="w-3.5 h-3.5">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </a>
              <a
                href={task.video_url!}
                download
                className="w-8 h-8 rounded-full bg-black/60 flex items-center justify-center hover:bg-black/80 transition-colors"
                title="Download"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" className="w-3.5 h-3.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
              </a>
            </div>

            {/* Upscale resolution picker */}
            {upscalePickerOpen && (
              <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/70">
                <div className="flex flex-col items-center gap-3 p-4">
                  <p className="text-white/60 text-xs">Upscale quality</p>
                  <div className="flex gap-2">
                    {["1080p", "4k"].map((r) => (
                      <button
                        key={r}
                        onClick={() => handleUpscale(r)}
                        className="px-4 py-2 rounded-lg bg-white text-black text-sm font-medium hover:bg-white/90 transition-colors"
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => setUpscalePickerOpen(false)}
                    className="text-white/30 text-xs hover:text-white/60 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : task.status === "failed" ? (
          <div className="text-center px-4">
            <p className="text-red-400 text-xs font-medium">Failed</p>
            <p className="text-white/40 text-[11px] mt-1">{task.error_message ?? task.error_code ?? ""}</p>
          </div>
        ) : (
          <div className="absolute inset-0 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/5 to-white/0 animate-shimmer bg-[length:200%_100%]" />
            <div className="absolute bottom-3 left-3 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-white/50 animate-pulse" />
              <span className="text-white/40 text-xs capitalize">{task.status}</span>
            </div>
          </div>
        )}
      </div>

      <div className="px-3 py-2">
        <p className="text-white/80 text-xs leading-relaxed line-clamp-2">{promptShort}</p>
        <p className="text-white/30 text-[11px] mt-1">{meta}</p>
      </div>
    </div>
  );
}
