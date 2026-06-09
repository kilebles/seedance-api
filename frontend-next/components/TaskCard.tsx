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

export default function TaskCard({ task: initial, onUpdate }: Props) {
  const [task, setTask] = useState(initial);
  const [playing, setPlaying] = useState(false);
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

  // BytePlus URLs expire after 24h; use updated_at as the reference point
  const videoAlive = task.video_url && task.updated_at
    ? Date.now() - new Date(task.updated_at).getTime() < 23.5 * 60 * 60 * 1000
    : false;

  const prompt = getPrompt(task.content_items);
  const promptShort = prompt.length > 100 ? prompt.slice(0, 100) + "…" : prompt;

  const res = task.resolution_actual ?? task.resolution_requested;
  const ratio = task.ratio_actual ?? task.ratio_requested;
  const dur = task.duration_actual ?? task.duration_requested;
  const upscale = task.upscale_resolution;

  const meta = [res, ratio, dur ? `${dur}s` : null, upscale ? `→${upscale}` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="rounded-xl overflow-hidden bg-white/5 border border-white/8 flex flex-col">
      {/* Thumbnail / video area */}
      <div className="relative aspect-video bg-zinc-900 flex items-center justify-center">
        {task.status === "succeeded" && videoAlive ? (
          playing ? (
            <video
              src={task.video_url!}
              controls
              autoPlay
              className="w-full h-full object-cover"
            />
          ) : (
            <button
              onClick={() => setPlaying(true)}
              className="absolute inset-0 w-full h-full group"
            >
              {task.last_frame_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={task.last_frame_url}
                  alt=""
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full bg-zinc-800" />
              )}
              {/* Play overlay */}
              <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="w-12 h-12 rounded-full bg-black/60 flex items-center justify-center">
                  <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5 ml-0.5">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
              </div>
            </button>
          )
        ) : task.status === "failed" ? (
          <div className="text-center px-4">
            <p className="text-red-400 text-xs font-medium">Failed</p>
            <p className="text-white/40 text-[11px] mt-1">{task.error_message ?? task.error_code ?? ""}</p>
          </div>
        ) : (
          /* queued / running — skeleton */
          <div className="absolute inset-0 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/5 to-white/0 animate-shimmer bg-[length:200%_100%]" />
            <div className="absolute bottom-3 left-3 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-white/50 animate-pulse" />
              <span className="text-white/40 text-xs capitalize">{task.status}</span>
            </div>
          </div>
        )}
      </div>

      {/* Meta */}
      <div className="px-3 py-2">
        <p className="text-white/80 text-xs leading-relaxed line-clamp-2">{promptShort}</p>
        <p className="text-white/30 text-[11px] mt-1">{meta}</p>
      </div>
    </div>
  );
}
