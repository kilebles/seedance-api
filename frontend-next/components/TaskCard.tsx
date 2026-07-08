"use client";

import { useEffect, useRef, useState } from "react";
import { Task, getTask, ContentItem } from "@/lib/api";

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
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setTask(initial);
  }, [initial]);

  useEffect(() => {
    if (task.status === "succeeded" || task.status === "failed" || task.status === "expired") return;

    timerRef.current = setTimeout(async () => {
      try {
        const updated = await getTask(task.id);
        setTask(updated);
        onUpdate(updated);
      } catch {/* ignore */}
    }, POLL_INTERVAL);

    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [task]);

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

  return (
    <div className="rounded-xl overflow-hidden bg-white/5 border border-white/8 flex flex-col">
      <div className="relative aspect-video bg-zinc-900 flex items-center justify-center">
        {task.status === "succeeded" && videoAlive ? (
          <div className="absolute inset-0 group">
            <VideoThumbnail src={task.video_url!} />
            <div className="absolute top-2 right-2 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity z-10">
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
