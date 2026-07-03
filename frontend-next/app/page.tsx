"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { Search } from "lucide-react";
import { Task, ImageTask, GenerationRequest, ImageGenerationRequest, submitTask, submitImageTask, listTasks, listImageTasks, getImageTask, ContentItem } from "@/lib/api";
import GenerateInput from "@/components/GenerateInput";
import TaskCard from "@/components/TaskCard";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { GenerateMode, ImageInputMode } from "@/components/Settings";

function getPrompt(items: ContentItem[]): string {
  return items.find((i) => i.type === "text")?.text ?? "";
}

function isExpired(t: Task): boolean {
  if (t.status !== "succeeded") return false;
  if (!t.video_url || !t.updated_at) return true;
  return Date.now() - new Date(t.updated_at).getTime() >= 23.5 * 60 * 60 * 1000;
}

type Tab = "video" | "image" | "billing";

export default function Home() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [imageTasks, setImageTasks] = useState<ImageTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useLocalStorage<"newest" | "oldest">("sd_sort", "newest");
  const [showFailed, setShowFailed] = useLocalStorage("sd_show_failed", false);
  const [showExpired, setShowExpired] = useLocalStorage("sd_show_expired", false);
  const [tab, setTab] = useLocalStorage<Tab>("sd_tab", "video");

  const [generateMode, setGenerateMode] = useLocalStorage<GenerateMode>("sd_generate_mode", "video");
  const [imageInputMode, setImageInputMode] = useLocalStorage<ImageInputMode>("sd_image_input_mode", "t2i");
  const [imageSize, setImageSize] = useLocalStorage("sd_image_size", "2048x2048");
  const [imageFormat, setImageFormat] = useLocalStorage("sd_image_format", "jpeg");

  useEffect(() => {
    listTasks().then(setTasks).catch(() => {});
    listImageTasks().then(setImageTasks).catch(() => {});
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

  const [videoModel, setVideoModel] = useLocalStorage("sd_video_model", "dreamina-seedance-2-0-260128");
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

  // Sync generateMode with active tab
  useEffect(() => {
    if (tab === "video") setGenerateMode("video");
    else if (tab === "image") setGenerateMode("image");
  }, [tab]);

  // Real-time refresh every 30s
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  // Today summary
  const todayStats = useMemo(() => {
    const todayStr = now.toISOString().slice(0, 10); // YYYY-MM-DD UTC
    const videos = tasks.filter((t) => t.status === "succeeded" && t.created_at.startsWith(todayStr));
    const images = imageTasks.filter((t) => t.status === "succeeded" && t.created_at.startsWith(todayStr));
    const videoTokens = videos.reduce((s, t) => s + (t.total_tokens ?? 0), 0);
    const imageTokens = images.reduce((s, t) => s + (t.total_tokens ?? 0), 0);
    return { videos: videos.length, images: images.length, videoTokens, imageTokens, total: videos.length + images.length, totalTokens: videoTokens + imageTokens };
  }, [tasks, imageTasks, now]);

  // Daily stats for chart (last 14 days)
  const dailyStats = useMemo(() => {
    const days: { date: string; label: string; tokens: number; videos: number; images: number }[] = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date(now);
      d.setUTCDate(d.getUTCDate() - i);
      const dateStr = d.toISOString().slice(0, 10);
      const dayVideos = tasks.filter((t) => t.status === "succeeded" && t.created_at.startsWith(dateStr));
      const dayImages = imageTasks.filter((t) => t.status === "succeeded" && t.created_at.startsWith(dateStr));
      const tokens = dayVideos.reduce((s, t) => s + (t.total_tokens ?? 0), 0) + dayImages.reduce((s, t) => s + (t.total_tokens ?? 0), 0);
      const label = d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
      days.push({ date: dateStr, label, tokens, videos: dayVideos.length, images: dayImages.length });
    }
    return days;
  }, [tasks, imageTasks, now]);

  // Billing stats
  const billingVideo = useMemo(() => {
    const done = tasks.filter((t) => t.status === "succeeded" && t.total_tokens);
    const byKey: Record<string, { count: number; total: number; completion: number }> = {};
    for (const t of done) {
      const key = `${t.model}|${t.resolution_actual ?? t.resolution_requested}|${t.ratio_actual ?? t.ratio_requested}|${t.duration_actual ?? t.duration_requested ?? "?"}`;
      if (!byKey[key]) byKey[key] = { count: 0, total: 0, completion: 0 };
      byKey[key].count++;
      byKey[key].total += t.total_tokens ?? 0;
      byKey[key].completion += t.completion_tokens ?? 0;
    }
    return { rows: byKey, totalTokens: done.reduce((s, t) => s + (t.total_tokens ?? 0), 0), count: done.length };
  }, [tasks]);

  const billingImage = useMemo(() => {
    const done = imageTasks.filter((t) => t.status === "succeeded" && t.total_tokens);
    const byKey: Record<string, { count: number; total: number; output: number }> = {};
    for (const t of done) {
      const key = `${t.model}|${t.image_size ?? t.size_requested ?? "?"}`;
      if (!byKey[key]) byKey[key] = { count: 0, total: 0, output: 0 };
      byKey[key].count++;
      byKey[key].total += t.total_tokens ?? 0;
      byKey[key].output += t.output_tokens ?? 0;
    }
    return { rows: byKey, totalTokens: done.reduce((s, t) => s + (t.total_tokens ?? 0), 0), count: done.length };
  }, [imageTasks]);

  return (
    <div className="h-screen overflow-hidden bg-zinc-950 text-white flex flex-col">
      {/* Top tabs */}
      <div className="shrink-0 px-6 pt-4 pb-0">
        <div className="max-w-5xl mx-auto flex gap-1">
          {(["video", "image", "billing"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-t-lg text-sm font-medium transition-colors capitalize ${
                tab === t
                  ? "bg-white/8 text-white border-b-2 border-white/30"
                  : "text-white/35 hover:text-white/60"
              }`}
            >
              {t === "billing" ? "Billing" : t === "video" ? "Video" : "Image"}
            </button>
          ))}
        </div>
      </div>

      {/* Toolbar — hidden on billing */}
      {tab !== "billing" && (
        <div className="shrink-0 px-6 pt-3 pb-3">
          <div className="max-w-5xl mx-auto flex items-center gap-3">
            <div className="flex-1 flex items-center gap-2 bg-white/5 rounded-xl px-3 py-2">
              <Search size={15} className="text-white/30 shrink-0" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by prompt..."
                className="flex-1 bg-transparent text-sm text-white placeholder-white/25 outline-none"
              />
            </div>

            {(["failed", "expired"] as const).map((key) => {
              if (key === "expired" && tab === "image") return null;
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
      )}

      {/* Results */}
      <main className="flex-1 overflow-y-auto px-6 py-3">
        {/* Video tab */}
        {tab === "video" && (
          <>
            {filtered.length === 0 ? (
              <div className="h-full min-h-[50vh] flex items-center justify-center">
                <p className="text-white/15 text-base">{search ? "No results" : "Generate your first video below"}</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
                {filtered.map((t) => <TaskCard key={t.id} task={t} onUpdate={handleUpdate} />)}
              </div>
            )}
          </>
        )}

        {/* Image tab */}
        {tab === "image" && (
          <>
            {filteredImages.length === 0 ? (
              <div className="h-full min-h-[50vh] flex items-center justify-center">
                <p className="text-white/15 text-base">{search ? "No results" : "Generate your first image below"}</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
                {filteredImages.map((t) => <ImageTaskCard key={t.id} task={t} onUpdate={(u) => setImageTasks((prev) => prev.map((x) => x.id === u.id ? u : x))} />)}
              </div>
            )}
          </>
        )}

        {/* Billing tab */}
        {tab === "billing" && (
          <div className="max-w-3xl mx-auto space-y-8 py-2">
            {/* Today summary */}
            <section>
              <div className="flex items-baseline gap-2 mb-3">
                <h2 className="text-sm font-medium text-white/50 uppercase tracking-wider">Today</h2>
                <span className="text-white/20 text-xs">{now.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Stat label="Videos" value={String(todayStats.videos)} />
                <Stat label="Images" value={String(todayStats.images)} />
                <Stat label="Video tokens" value={todayStats.videoTokens.toLocaleString()} />
                <Stat label="Image tokens" value={todayStats.imageTokens.toLocaleString()} />
              </div>
              {todayStats.total === 0 && (
                <p className="text-white/20 text-xs mt-2">Nothing generated today yet</p>
              )}
            </section>

            <div className="border-t border-white/6" />

            {/* Daily chart */}
            <section>
              <h2 className="text-sm font-medium text-white/50 uppercase tracking-wider mb-4">Last 14 days</h2>
              <DailyChart days={dailyStats} />
            </section>

            <div className="border-t border-white/6" />

            {/* Video billing */}
            <section>
              <h2 className="text-sm font-medium text-white/50 uppercase tracking-wider mb-3">Video</h2>
              {billingVideo.count === 0 ? (
                <p className="text-white/20 text-sm">No data yet</p>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <Stat label="Completed" value={String(billingVideo.count)} />
                    <Stat label="Total tokens" value={billingVideo.totalTokens.toLocaleString()} />
                    <Stat label="Avg / task" value={Math.round(billingVideo.totalTokens / billingVideo.count).toLocaleString()} />
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-white/30 text-xs border-b border-white/8">
                        <th className="text-left pb-2 font-normal">Model</th>
                        <th className="text-left pb-2 font-normal">Resolution</th>
                        <th className="text-left pb-2 font-normal">Ratio</th>
                        <th className="text-left pb-2 font-normal">Duration</th>
                        <th className="text-right pb-2 font-normal">Tasks</th>
                        <th className="text-right pb-2 font-normal">Total tokens</th>
                        <th className="text-right pb-2 font-normal">Avg tokens</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(billingVideo.rows).map(([key, v]) => {
                        const [model, res, ratio, dur] = key.split("|");
                        const modelShort = model.replace("dreamina-", "").replace("-260128", "").replace("-260615", "").replace("-251215", "").replace("-250528", "");
                        return (
                          <tr key={key} className="border-b border-white/5 text-white/70">
                            <td className="py-2 pr-3">{modelShort}</td>
                            <td className="py-2 pr-3">{res}</td>
                            <td className="py-2 pr-3">{ratio}</td>
                            <td className="py-2 pr-3">{dur}s</td>
                            <td className="py-2 text-right">{v.count}</td>
                            <td className="py-2 text-right">{v.total.toLocaleString()}</td>
                            <td className="py-2 text-right">{Math.round(v.total / v.count).toLocaleString()}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </>
              )}
            </section>

            {/* Image billing */}
            <section>
              <h2 className="text-sm font-medium text-white/50 uppercase tracking-wider mb-3">Image</h2>
              {billingImage.count === 0 ? (
                <p className="text-white/20 text-sm">No data yet</p>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <Stat label="Completed" value={String(billingImage.count)} />
                    <Stat label="Total tokens" value={billingImage.totalTokens.toLocaleString()} />
                    <Stat label="Avg / task" value={Math.round(billingImage.totalTokens / billingImage.count).toLocaleString()} />
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-white/30 text-xs border-b border-white/8">
                        <th className="text-left pb-2 font-normal">Model</th>
                        <th className="text-left pb-2 font-normal">Size</th>
                        <th className="text-right pb-2 font-normal">Tasks</th>
                        <th className="text-right pb-2 font-normal">Total tokens</th>
                        <th className="text-right pb-2 font-normal">Output tokens</th>
                        <th className="text-right pb-2 font-normal">Avg tokens</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(billingImage.rows).map(([key, v]) => {
                        const [model, size] = key.split("|");
                        return (
                          <tr key={key} className="border-b border-white/5 text-white/70">
                            <td className="py-2 pr-3">{model}</td>
                            <td className="py-2 pr-3">{size}</td>
                            <td className="py-2 text-right">{v.count}</td>
                            <td className="py-2 text-right">{v.total.toLocaleString()}</td>
                            <td className="py-2 text-right">{v.output.toLocaleString()}</td>
                            <td className="py-2 text-right">{Math.round(v.total / v.count).toLocaleString()}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </>
              )}
            </section>
          </div>
        )}
      </main>

      {/* Bottom input — hidden on billing */}
      {tab !== "billing" && (
        <div className="shrink-0 px-6 pb-6 pt-3">
          {error && <p className="text-red-400 text-sm mb-2 text-center">{error}</p>}
          <div className="max-w-5xl mx-auto">
            <GenerateInput
              onSubmit={handleSubmit}
              onSubmitImage={handleSubmitImage}
              loading={loading}
              generateMode={generateMode} setGenerateMode={setGenerateMode}
              videoModel={videoModel} setVideoModel={setVideoModel}
              imageInputMode={imageInputMode} setImageInputMode={setImageInputMode}
              imageSize={imageSize} setImageSize={setImageSize}
              imageFormat={imageFormat} setImageFormat={setImageFormat}
              ratio={ratio} setRatio={setRatio}
              resolution={resolution} setResolution={setResolution}
              duration={duration} setDuration={setDuration}
              generateAudio={generateAudio} setGenerateAudio={setGenerateAudio}
              seed={seed} setSeed={setSeed}
              upscaleResolution={upscaleResolution} setUpscaleResolution={setUpscaleResolution}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function DailyChart({ days }: { days: { label: string; tokens: number; videos: number; images: number }[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const maxTokens = Math.max(...days.map((d) => d.tokens), 1);
  const H = 80;
  const barW = 14;
  const gap = 6;
  const totalW = days.length * (barW + gap) - gap;

  return (
    <div className="space-y-2">
      <svg width="100%" viewBox={`0 0 ${totalW} ${H + 24}`} className="overflow-visible">
        {days.map((d, i) => {
          const x = i * (barW + gap);
          const barH = d.tokens > 0 ? Math.max(3, Math.round((d.tokens / maxTokens) * H)) : 2;
          const y = H - barH;
          const isHov = hovered === i;
          const isToday = d.label === "Today";
          return (
            <g key={i} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}>
              <rect x={x} y={y} width={barW} height={barH} rx={3}
                fill={isToday ? "rgba(255,255,255,0.7)" : isHov ? "rgba(255,255,255,0.25)" : "rgba(255,255,255,0.12)"}
                className="transition-colors duration-150 cursor-default"
              />
              {/* empty bar bg */}
              {d.tokens === 0 && (
                <rect x={x} y={H - 2} width={barW} height={2} rx={1} fill="rgba(255,255,255,0.06)" />
              )}
              {/* x label — day number only */}
              <text x={x + barW / 2} y={H + 14} textAnchor="middle" fontSize={8} fill={isToday ? "rgba(255,255,255,0.55)" : "rgba(255,255,255,0.18)"}>
                {d.label.split(" ")[0]}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      <div className="h-10">
        {hovered !== null && (
          <div className="flex items-center gap-4 text-xs text-white/50">
            <span className="text-white/70 font-medium">{days[hovered].label}</span>
            <span>{days[hovered].tokens.toLocaleString()} tokens</span>
            <span>{days[hovered].videos} videos</span>
            <span>{days[hovered].images} images</span>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white/5 rounded-xl px-4 py-3">
      <p className="text-white/35 text-xs mb-1">{label}</p>
      <p className="text-white text-lg font-medium">{value}</p>
    </div>
  );
}

function ImageTaskCard({ task: initial, onUpdate }: { task: ImageTask; onUpdate: (t: ImageTask) => void }) {
  const [task, setTask] = useState(initial);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { setTask(initial); }, [initial]);

  useEffect(() => {
    if (task.status === "succeeded" || task.status === "failed") return;
    timerRef.current = setTimeout(async () => {
      try {
        const updated = await getImageTask(task.id);
        setTask(updated);
        onUpdate(updated);
      } catch {/* ignore */}
    }, 3000);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [task]);

  const promptShort = task.prompt.length > 100 ? task.prompt.slice(0, 100) + "…" : task.prompt;
  const meta = task.image_size ?? task.size_requested ?? "";

  return (
    <div className="rounded-xl overflow-hidden bg-white/5 border border-white/8 flex flex-col">
      <div className="relative aspect-video bg-zinc-900 flex items-center justify-center">
        {task.status === "succeeded" && task.image_url ? (
          <div className="relative w-full h-full group">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={task.image_url} alt={task.prompt} className="w-full h-full object-cover" />
            <div className="absolute inset-0 flex items-center justify-center gap-2 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity">
              <a href={task.image_url} target="_blank" rel="noopener noreferrer" className="w-9 h-9 rounded-full bg-black/60 flex items-center justify-center hover:bg-black/80 transition-colors" title="Open">
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" className="w-4 h-4"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" /></svg>
              </a>
              <a href={task.image_url} download className="w-9 h-9 rounded-full bg-black/60 flex items-center justify-center hover:bg-black/80 transition-colors" title="Download">
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" className="w-4 h-4"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
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
              <span className="text-white/40 text-xs">generating</span>
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
