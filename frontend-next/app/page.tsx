"use client";

import { useState, useEffect, useMemo } from "react";
import { Search } from "lucide-react";
import { Task, ImageTask, GenerationRequest, ImageGenerationRequest, submitTask, submitImageTask, listTasks, ContentItem } from "@/lib/api";
import GenerateInput from "@/components/GenerateInput";
import TaskCard from "@/components/TaskCard";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { GenerateMode } from "@/components/Settings";

function getPrompt(items: ContentItem[]): string {
  return items.find((i) => i.type === "text")?.text ?? "";
}

function isExpired(t: Task): boolean {
  if (t.status !== "succeeded") return false;
  if (!t.video_url || !t.updated_at) return true;
  return Date.now() - new Date(t.updated_at).getTime() >= 23.5 * 60 * 60 * 1000;
}

export default function Home() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [imageTasks, setImageTasks] = useState<ImageTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useLocalStorage<"newest" | "oldest">("sd_sort", "newest");
  const [showFailed, setShowFailed] = useLocalStorage("sd_show_failed", false);
  const [showExpired, setShowExpired] = useLocalStorage("sd_show_expired", false);

  const [generateMode, setGenerateMode] = useLocalStorage<GenerateMode>("sd_generate_mode", "video");

  useEffect(() => {
    listTasks().then(setTasks).catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = tasks.filter((t) => {
      if (t.status === "failed" && !showFailed) return false;
      if (isExpired(t) && !showExpired) return false;
      return true;
    });
    if (q) list = list.filter((t) => getPrompt(t.content_items).toLowerCase().includes(q));
    list = [...list].sort((a, b) => {
      const diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return sort === "newest" ? -diff : diff;
    });
    return list;
  }, [tasks, search, sort, showFailed, showExpired]);

  const filteredImages = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = imageTasks.filter((t) => {
      if (t.status === "failed" && !showFailed) return false;
      return true;
    });
    if (q) list = list.filter((t) => t.prompt.toLowerCase().includes(q));
    list = [...list].sort((a, b) => {
      const diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return sort === "newest" ? -diff : diff;
    });
    return list;
  }, [imageTasks, search, sort, showFailed]);

  const [ratio, setRatio] = useLocalStorage("sd_ratio", "16:9");
  const [resolution, setResolution] = useLocalStorage("sd_resolution", "720p");
  const [duration, setDuration] = useLocalStorage("sd_duration", 8);
  const [generateAudio, setGenerateAudio] = useLocalStorage("sd_audio", true);
  const [seed, setSeed] = useLocalStorage<number | null>("sd_seed", null);
  const [upscaleResolution, setUpscaleResolution] = useLocalStorage<string | null>("sd_upscale", null);

  async function handleSubmit(req: GenerationRequest) {
    setLoading(true);
    setError(null);
    try {
      const task = await submitTask(req);
      setTasks((prev) => [task, ...prev]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitImage(req: ImageGenerationRequest) {
    setLoading(true);
    setError(null);
    try {
      const task = await submitImageTask(req);
      setImageTasks((prev) => [task, ...prev]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function handleUpdate(updated: Task) {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  }

  const showImages = generateMode === "image";
  const displayList = showImages ? filteredImages : filtered;

  return (
    <div className="h-screen overflow-hidden bg-zinc-950 text-white flex flex-col">
      {/* Toolbar */}
      <div className="shrink-0 px-6 pt-5 pb-3">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          {/* Search */}
          <div className="flex-1 flex items-center gap-2 bg-white/5 rounded-xl px-3 py-2">
            <Search size={15} className="text-white/30 shrink-0" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by prompt..."
              className="flex-1 bg-transparent text-sm text-white placeholder-white/25 outline-none"
            />
          </div>

          {/* Checkboxes */}
          {(["failed", "expired"] as const).map((key) => {
            if (key === "expired" && showImages) return null;
            const checked = key === "failed" ? showFailed : showExpired;
            const toggle = key === "failed" ? setShowFailed : setShowExpired;
            return (
              <label key={key} className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => toggle(e.target.checked)}
                  className="accent-white w-3.5 h-3.5"
                />
                <span className="text-xs text-white/40">{key === "failed" ? "Failed" : "Expired"}</span>
              </label>
            );
          })}

          {/* Sort */}
          <div className="flex gap-1 bg-white/5 rounded-xl p-1">
            {(["newest", "oldest"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSort(s)}
                className={`px-3 py-1 rounded-lg text-xs transition-colors ${
                  sort === s ? "bg-white/15 text-white" : "text-white/35 hover:text-white/60"
                }`}
              >
                {s === "newest" ? "Newest" : "Oldest"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results grid */}
      <main className="flex-1 overflow-y-auto px-6 py-3">
        {displayList.length === 0 && !loading && (
          <div className="h-full min-h-[50vh] flex items-center justify-center">
            <p className="text-white/15 text-base">
              {search ? "No results" : showImages ? "Generate your first image below" : "Generate your first video below"}
            </p>
          </div>
        )}
        {displayList.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
            {showImages
              ? filteredImages.map((t) => <ImageTaskCard key={t.id} task={t} />)
              : filtered.map((t) => <TaskCard key={t.id} task={t} onUpdate={handleUpdate} />)
            }
          </div>
        )}
      </main>

      {/* Bottom input */}
      <div className="shrink-0 px-6 pb-6 pt-3">
        {error && <p className="text-red-400 text-sm mb-2 text-center">{error}</p>}
        <div className="max-w-5xl mx-auto">
          <GenerateInput
            onSubmit={handleSubmit}
            onSubmitImage={handleSubmitImage}
            loading={loading}
            generateMode={generateMode} setGenerateMode={setGenerateMode}
            ratio={ratio} setRatio={setRatio}
            resolution={resolution} setResolution={setResolution}
            duration={duration} setDuration={setDuration}
            generateAudio={generateAudio} setGenerateAudio={setGenerateAudio}
            seed={seed} setSeed={setSeed}
            upscaleResolution={upscaleResolution} setUpscaleResolution={setUpscaleResolution}
          />
        </div>
      </div>
    </div>
  );
}

function ImageTaskCard({ task }: { task: ImageTask }) {
  const promptShort = task.prompt.length > 100 ? task.prompt.slice(0, 100) + "…" : task.prompt;
  const meta = task.image_size ?? task.size_requested ?? "";

  return (
    <div className="rounded-xl overflow-hidden bg-white/5 border border-white/8 flex flex-col">
      <div className="relative aspect-video bg-zinc-900 flex items-center justify-center">
        {task.status === "succeeded" && task.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={task.image_url} alt={task.prompt} className="w-full h-full object-cover" />
        ) : task.status === "failed" ? (
          <div className="text-center px-4">
            <p className="text-red-400 text-xs font-medium">Failed</p>
            <p className="text-white/40 text-[11px] mt-1">{task.error_message ?? task.error_code ?? ""}</p>
          </div>
        ) : (
          <div className="w-full h-full bg-zinc-800" />
        )}
      </div>
      <div className="px-3 py-2">
        <p className="text-white/80 text-xs leading-relaxed line-clamp-2">{promptShort}</p>
        <p className="text-white/30 text-[11px] mt-1">{meta}</p>
      </div>
    </div>
  );
}
