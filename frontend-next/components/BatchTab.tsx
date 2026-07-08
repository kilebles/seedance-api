"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Upload, X, Square, ChevronLeft, Plus } from "lucide-react";
import {
  Task, BatchSummary,
  submitBatch, cancelTasksBulk, listBatchTasks, listBatches, retryBatchFailed, batchUpscale, getTask,
  TaskStatus,
} from "@/lib/api";
import { VIDEO_MODELS, VideoModelDef } from "@/components/Settings";

const UPSCALE_OPTIONS = ["1080p", "4k"];
const POLL_INTERVAL = 4000;
const TERMINAL: TaskStatus[] = ["succeeded", "failed", "expired", "cancelled"];

const STATUS_DOT: Record<string, string> = {
  queued: "bg-white/30",
  running: "bg-blue-400 animate-pulse",
  succeeded: "bg-green-400",
  failed: "bg-red-400",
  expired: "bg-yellow-500",
  cancelled: "bg-white/20",
};

function Pill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded-full text-sm transition-colors ${
        active ? "bg-white text-black font-medium" : "bg-white/8 text-white/55 hover:bg-white/14 hover:text-white/75"
      }`}
    >
      {children}
    </button>
  );
}

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${on ? "bg-white" : "bg-white/20"}`}
    >
      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-black transition-all ${on ? "left-5" : "left-0.5"}`} />
    </button>
  );
}

// ─── Project list ────────────────────────────────────────────────────────────

function BatchList({
  batches,
  onSelect,
  onNew,
}: {
  batches: BatchSummary[];
  onSelect: (b: BatchSummary) => void;
  onNew: () => void;
}) {
  return (
    <div className="max-w-5xl mx-auto py-4 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-white/40">Batches</p>
        <button
          onClick={onNew}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/8 text-white/60 hover:bg-white/14 hover:text-white text-sm transition-colors"
        >
          <Plus size={13} />
          New batch
        </button>
      </div>

      {batches.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <p className="text-white/20 text-sm">No batches yet</p>
          <button
            onClick={onNew}
            className="px-4 py-2 rounded-xl bg-white text-black text-sm font-medium hover:bg-white/90 transition-colors"
          >
            Create first batch
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {batches.map((b) => {
            const progress = b.total > 0 ? b.done / b.total : 0;
            const allDone = b.done === b.total;
            const date = b.created_at
              ? new Date(b.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
              : "";
            return (
              <button
                key={b.batch_id}
                onClick={() => onSelect(b)}
                className="text-left bg-white/3 hover:bg-white/6 rounded-2xl p-4 transition-colors space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm text-white/80 font-medium truncate leading-tight">{b.name}</p>
                  <span className="text-xs text-white/25 shrink-0 mt-0.5">{date}</span>
                </div>
                <div className="w-full h-0.5 bg-white/8 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${allDone ? "bg-green-400/60" : "bg-white/40"}`}
                    style={{ width: `${progress * 100}%` }}
                  />
                </div>
                <div className="flex items-center gap-3 text-xs text-white/35">
                  <span>{b.done} / {b.total}</span>
                  {b.failed > 0 && <span className="text-red-400/60">{b.failed} failed</span>}
                  {b.resolution && <span>{b.resolution}</span>}
                  {b.upscale_resolution && <span>→{b.upscale_resolution}</span>}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── New batch form ──────────────────────────────────────────────────────────

function NewBatchForm({ onSubmitted, onCancel }: {
  onSubmitted: (batchId: string) => void;
  onCancel: () => void;
}) {
  const [model, setModel] = useState("dreamina-seedance-2-0-fast-260128");
  const [ratio, setRatio] = useState("16:9");
  const [resolution, setResolution] = useState("720p");
  const [duration, setDuration] = useState(8);
  const [generateAudio, setGenerateAudio] = useState(true);
  const [upscaleResolution, setUpscaleResolution] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const modelDef: VideoModelDef = VIDEO_MODELS.find((m) => m.id === model) ?? VIDEO_MODELS[0];

  function handleModelChange(id: string) {
    const def = VIDEO_MODELS.find((m) => m.id === id);
    if (!def) return;
    setModel(id);
    if (!def.resolutions.includes(resolution)) setResolution(def.resolutions[1] ?? def.resolutions[0]);
    if (!def.ratios.includes(ratio)) setRatio("16:9");
    if (!def.durations.includes(duration)) setDuration(def.durations[Math.min(4, def.durations.length - 1)]);
    if (!def.supportsAudio && generateAudio) setGenerateAudio(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f && f.name.endsWith(".xlsx")) setFile(f);
  }

  async function handleSubmit() {
    if (!file) return;
    setSubmitting(true);
    setError(null);
    try {
      const tasks = await submitBatch(file, {
        model, ratio, resolution, duration, generate_audio: generateAudio,
        ...(upscaleResolution ? { upscale_resolution: upscaleResolution } : {}),
      });
      if (tasks.length === 0) { setError("No tasks returned"); return; }
      const first = await getTask(tasks[0].id);
      const bid = first.batch_id;
      if (!bid) { setError("No batch_id returned"); return; }
      onSubmitted(bid);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto py-4 space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onCancel} className="text-white/30 hover:text-white/60 transition-colors">
          <ChevronLeft size={18} />
        </button>
        <p className="text-sm text-white/60">New batch</p>
      </div>

      {/* Settings */}
      <div className="space-y-5 bg-white/3 rounded-2xl p-5">
        <div>
          <p className="text-xs text-white/35 mb-2">Model</p>
          <div className="flex flex-col gap-1.5">
            {VIDEO_MODELS.map((m) => (
              <Pill key={m.id} active={model === m.id} onClick={() => handleModelChange(m.id)}>{m.label}</Pill>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs text-white/35 mb-2">Aspect ratio</p>
          <div className="flex flex-wrap gap-1.5">
            {modelDef.ratios.map((r) => <Pill key={r} active={ratio === r} onClick={() => setRatio(r)}>{r}</Pill>)}
          </div>
        </div>
        <div>
          <p className="text-xs text-white/35 mb-2">Resolution</p>
          <div className="flex flex-wrap gap-1.5">
            {modelDef.resolutions.map((r) => <Pill key={r} active={resolution === r} onClick={() => setResolution(r)}>{r}</Pill>)}
          </div>
        </div>
        <div>
          <p className="text-xs text-white/35 mb-2">Duration</p>
          <div className="flex flex-wrap gap-1.5">
            {modelDef.durations.map((d) => <Pill key={d} active={duration === d} onClick={() => setDuration(d)}>{d}s</Pill>)}
          </div>
        </div>
        {modelDef.supportsAudio && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-white/55">Generate audio</p>
            <Toggle on={generateAudio} onToggle={() => setGenerateAudio(!generateAudio)} />
          </div>
        )}
        <div>
          <div className="flex items-center justify-between">
            <p className="text-sm text-white/55">Upscale (Topaz)</p>
            <Toggle on={!!upscaleResolution} onToggle={() => setUpscaleResolution(upscaleResolution ? null : "1080p")} />
          </div>
          {upscaleResolution && (
            <div className="flex gap-1.5 mt-2">
              {UPSCALE_OPTIONS.map((o) => <Pill key={o} active={upscaleResolution === o} onClick={() => setUpscaleResolution(o)}>{o}</Pill>)}
            </div>
          )}
        </div>
      </div>

      {/* File upload */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        className={`rounded-2xl border-2 border-dashed cursor-pointer flex flex-col items-center justify-center py-10 gap-3 transition-colors ${
          dragOver ? "border-white/40 bg-white/5" : "border-white/12 hover:border-white/25 hover:bg-white/3"
        }`}
      >
        <Upload size={24} className="text-white/30" />
        {file ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-white/70">{file.name}</span>
            <button onClick={(e) => { e.stopPropagation(); setFile(null); }} className="text-white/30 hover:text-white/60">
              <X size={14} />
            </button>
          </div>
        ) : (
          <>
            <p className="text-sm text-white/40">Drop xlsx file here or click to browse</p>
            <p className="text-xs text-white/20">Columns: <code className="text-white/30">number</code>, <code className="text-white/30">prompt</code></p>
          </>
        )}
      </div>
      <input ref={fileRef} type="file" accept=".xlsx" className="hidden" onChange={(e) => { setFile(e.target.files?.[0] ?? null); e.target.value = ""; }} />

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={!file || submitting}
        className="w-full py-3 rounded-xl bg-white text-black text-sm font-medium hover:bg-white/90 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Starting batch..." : "Start batch"}
      </button>
    </div>
  );
}

// ─── Batch detail ────────────────────────────────────────────────────────────

function BatchDetail({ batchId, onBack }: { batchId: string; onBack: () => void }) {
  const [rows, setRows] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [stopping, setStopping] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [upscaleRes, setUpscaleRes] = useState<string | null>(null); // null = picker closed
  const [upscaling, setUpscaling] = useState(false);
  const [upscaleMsg, setUpscaleMsg] = useState<string | null>(null);

  const failedCount = rows.filter((r) => r.status === "failed").length;
  const succeededCount = rows.filter((r) => r.status === "succeeded").length;
  const allDone = rows.length > 0 && rows.every((r) => TERMINAL.includes(r.status));
  const doneCount = rows.filter((r) => TERMINAL.includes(r.status)).length;
  const progress = rows.length > 0 ? succeededCount / rows.length : 0;

  const batchIdRef = useRef(batchId);

  const scheduleNextPoll = useCallback(() => {
    const timer = setTimeout(async () => {
      try {
        const tasks = await listBatchTasks(batchIdRef.current);
        setRows(tasks);
        const stillPending = tasks.filter((r) => !TERMINAL.includes(r.status));
        if (stillPending.length > 0) scheduleNextPoll();
      } catch {
        scheduleNextPoll();
      }
    }, POLL_INTERVAL);
    return timer;
  }, []);

  useEffect(() => {
    batchIdRef.current = batchId;
    setLoading(true);
    listBatchTasks(batchId).then((tasks) => {
      setRows(tasks);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [batchId]);

  useEffect(() => {
    if (loading || allDone) return;
    const timer = scheduleNextPoll();
    return () => clearTimeout(timer);
  }, [loading, allDone, scheduleNextPoll]);

  async function handleStop() {
    const cancellable = rows.filter((r) => !TERMINAL.includes(r.status)).map((r) => r.id);
    if (cancellable.length === 0) return;
    setStopping(true);
    try {
      await cancelTasksBulk(cancellable);
      const tasks = await listBatchTasks(batchId);
      setRows(tasks);
    } catch {/* ignore */} finally {
      setStopping(false);
    }
  }

  async function handleRetryFailed() {
    setRetrying(true);
    try {
      await retryBatchFailed(batchId);
      const tasks = await listBatchTasks(batchId);
      setRows(tasks);
    } catch {/* ignore */} finally {
      setRetrying(false);
    }
  }

  async function handleUpscale() {
    if (!upscaleRes) return;
    setUpscaling(true);
    setUpscaleMsg(null);
    try {
      const res = await batchUpscale(batchId, upscaleRes);
      setUpscaleMsg(res.queued > 0 ? `Queued ${res.queued} videos for upscale → ${res.resolution}` : "Nothing to upscale");
      setUpscaleRes(null);
    } catch (e) {
      setUpscaleMsg(e instanceof Error ? e.message : "Error");
    } finally {
      setUpscaling(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto py-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-white/30 hover:text-white/60 transition-colors">
            <ChevronLeft size={18} />
          </button>
          <span className="text-sm text-white/60">{allDone ? "Done" : "Running"}</span>
          <span className="text-sm text-white/30">{succeededCount} / {rows.length}</span>
          {failedCount > 0 && <span className="text-xs text-red-400/70">{failedCount} failed</span>}
        </div>
        <div className="flex items-center gap-2">
          {succeededCount > 0 && upscaleRes === null && (
            <button
              onClick={() => setUpscaleRes("1080p")}
              className="px-3 py-1.5 rounded-lg bg-white/8 text-white/60 hover:bg-white/14 hover:text-white text-sm transition-colors"
            >
              Upscale (Topaz)
            </button>
          )}
          {failedCount > 0 && (
            <button
              onClick={handleRetryFailed}
              disabled={retrying}
              className="px-3 py-1.5 rounded-lg bg-white/8 text-white/60 hover:bg-white/14 hover:text-white text-sm transition-colors disabled:opacity-40"
            >
              {retrying ? "Retrying..." : `Retry failed (${failedCount})`}
            </button>
          )}
          {!allDone && (
            <button
              onClick={handleStop}
              disabled={stopping}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/8 text-white/60 hover:bg-white/14 hover:text-white text-sm transition-colors disabled:opacity-40"
            >
              <Square size={12} />
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Upscale resolution picker */}
      {upscaleRes !== null && (
        <div className="flex items-center gap-3 bg-white/3 rounded-xl px-4 py-3">
          <span className="text-sm text-white/50 shrink-0">Upscale quality</span>
          <div className="flex gap-1.5">
            {["1080p", "4k"].map((o) => (
              <Pill key={o} active={upscaleRes === o} onClick={() => setUpscaleRes(o)}>{o}</Pill>
            ))}
          </div>
          <div className="flex gap-2 ml-auto">
            <button
              onClick={() => { setUpscaleRes(null); setUpscaleMsg(null); }}
              className="px-3 py-1.5 rounded-lg bg-white/8 text-white/40 hover:text-white text-sm transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleUpscale}
              disabled={upscaling}
              className="px-3 py-1.5 rounded-lg bg-white text-black text-sm font-medium hover:bg-white/90 disabled:opacity-40 transition-colors"
            >
              {upscaling ? "Starting..." : `Run on ${succeededCount} videos`}
            </button>
          </div>
        </div>
      )}
      {upscaleMsg && (
        <p className={`text-xs ${upscaleMsg.startsWith("Queued") ? "text-green-400/70" : "text-red-400/70"}`}>{upscaleMsg}</p>
      )}

      {/* Progress bar */}
      <div className="w-full h-1 bg-white/8 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${allDone ? "bg-green-400/60" : "bg-white/60"}`}
          style={{ width: `${progress * 100}%` }}
        />
      </div>

      {/* Task table */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <span className="text-white/30 text-sm">Loading...</span>
        </div>
      ) : (
        <div className="rounded-xl border border-white/8 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/8 text-white/30 text-xs">
                <th className="text-left px-4 py-2.5 font-normal w-24">#</th>
                <th className="text-left px-4 py-2.5 font-normal">Status</th>
                <th className="text-left px-4 py-2.5 font-normal text-white/20">Error</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-white/5 last:border-0">
                  <td className="px-4 py-2.5 text-white/50 font-mono text-xs">{row.name ?? row.id.slice(0, 8)}</td>
                  <td className="px-4 py-2.5">
                    <span className="flex items-center gap-2">
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[row.status] ?? "bg-white/20"}`} />
                      <span className={`text-xs ${row.status === "succeeded" ? "text-white/70" : row.status === "failed" ? "text-red-400" : "text-white/40"}`}>
                        {row.status}
                      </span>
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-red-400/70 text-xs truncate max-w-xs">
                    {row.error_message ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

type View = { kind: "list" } | { kind: "new" } | { kind: "detail"; batchId: string };

export default function BatchTab() {
  const [view, setView] = useState<View>({ kind: "list" });
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);

  async function refreshList() {
    setLoadingList(true);
    try {
      setBatches(await listBatches());
    } catch {/* ignore */} finally {
      setLoadingList(false);
    }
  }

  useEffect(() => { refreshList(); }, []);

  // Refresh list when returning to it
  useEffect(() => {
    if (view.kind === "list") refreshList();
  }, [view]);

  if (view.kind === "new") {
    return (
      <NewBatchForm
        onSubmitted={(batchId) => setView({ kind: "detail", batchId })}
        onCancel={() => setView({ kind: "list" })}
      />
    );
  }

  if (view.kind === "detail") {
    return <BatchDetail batchId={view.batchId} onBack={() => setView({ kind: "list" })} />;
  }

  // list
  if (loadingList) {
    return (
      <div className="max-w-3xl mx-auto py-4 flex items-center justify-center h-40">
        <span className="text-white/30 text-sm">Loading...</span>
      </div>
    );
  }

  return (
    <BatchList
      batches={batches}
      onSelect={(b) => setView({ kind: "detail", batchId: b.batch_id })}
      onNew={() => setView({ kind: "new" })}
    />
  );
}
