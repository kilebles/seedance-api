"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Upload, X, Square } from "lucide-react";
import { BatchTask, submitBatch, cancelTasksBulk, getTask, TaskStatus } from "@/lib/api";
import { VIDEO_MODELS, VideoModelDef } from "@/components/Settings";

const UPSCALE_OPTIONS = ["1080p", "4k"];

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

const STATUS_DOT: Record<string, string> = {
  queued: "bg-white/30",
  running: "bg-blue-400 animate-pulse",
  succeeded: "bg-green-400",
  failed: "bg-red-400",
  expired: "bg-yellow-500",
  cancelled: "bg-white/20",
};

interface RowState {
  id: string;
  name: string;
  prompt: string;
  status: TaskStatus;
  error_message: string | null;
}

const TERMINAL: TaskStatus[] = ["succeeded", "failed", "expired", "cancelled"];
const POLL_INTERVAL = 4000;

export default function BatchTab() {
  // settings
  const [model, setModel] = useState("dreamina-seedance-2-0-fast-260128");
  const [ratio, setRatio] = useState("16:9");
  const [resolution, setResolution] = useState("720p");
  const [duration, setDuration] = useState(8);
  const [generateAudio, setGenerateAudio] = useState(true);
  const [upscaleResolution, setUpscaleResolution] = useState<string | null>(null);

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

  // file
  const [file, setFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f && f.name.endsWith(".xlsx")) setFile(f);
  }

  // batch state
  const [rows, setRows] = useState<RowState[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  const isActive = rows.length > 0;
  const doneCount = rows.filter((r) => TERMINAL.includes(r.status)).length;
  const progress = rows.length > 0 ? doneCount / rows.length : 0;
  const allDone = rows.length > 0 && doneCount === rows.length;

  // polling
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rowsRef = useRef<RowState[]>(rows);
  useEffect(() => { rowsRef.current = rows; }, [rows]);

  const scheduleNextPoll = useCallback(() => {
    pollRef.current = setTimeout(async () => {
      const current = rowsRef.current;
      const pending = current.filter((r) => !TERMINAL.includes(r.status));
      if (pending.length === 0) return;

      const updates = await Promise.allSettled(pending.map((r) => getTask(r.id)));
      setRows((prev) =>
        prev.map((row) => {
          const idx = pending.findIndex((p) => p.id === row.id);
          if (idx === -1) return row;
          const res = updates[idx];
          if (res.status === "fulfilled") {
            return { ...row, status: res.value.status, error_message: res.value.error_message };
          }
          return row;
        })
      );

      // schedule next only if still pending
      const stillPending = rowsRef.current.filter((r) => !TERMINAL.includes(r.status));
      if (stillPending.length > 0) scheduleNextPoll();
    }, POLL_INTERVAL);
  }, []);

  useEffect(() => {
    if (!isActive || allDone) {
      if (pollRef.current) clearTimeout(pollRef.current);
      return;
    }
    scheduleNextPoll();
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
  }, [isActive, allDone, scheduleNextPoll]);

  async function handleSubmit() {
    if (!file) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const tasks = await submitBatch(file, {
        model, ratio, resolution, duration, generate_audio: generateAudio,
        ...(upscaleResolution ? { upscale_resolution: upscaleResolution } : {}),
      });

      // parse prompts from xlsx client-side is complex — store what API returns
      setRows(tasks.map((t) => ({
        id: t.id,
        name: t.name,
        prompt: "",
        status: t.status,
        error_message: t.error_message,
      })));
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStop() {
    const cancellable = rows.filter((r) => !TERMINAL.includes(r.status)).map((r) => r.id);
    if (cancellable.length === 0) return;
    setStopping(true);
    try {
      await cancelTasksBulk(cancellable);
      setRows((prev) => prev.map((r) =>
        cancellable.includes(r.id) ? { ...r, status: "cancelled" } : r
      ));
    } catch {
      // ignore
    } finally {
      setStopping(false);
    }
  }

  function handleReset() {
    setRows([]);
    setFile(null);
    setSubmitError(null);
  }

  return (
    <div className="max-w-3xl mx-auto py-4 space-y-6">

      {!isActive ? (
        <>
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
                <button
                  onClick={(e) => { e.stopPropagation(); setFile(null); }}
                  className="text-white/30 hover:text-white/60"
                >
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
          <input ref={fileRef} type="file" accept=".xlsx" className="hidden" onChange={handleFileChange} />

          {submitError && <p className="text-red-400 text-sm">{submitError}</p>}

          <button
            onClick={handleSubmit}
            disabled={!file || submitting}
            className="w-full py-3 rounded-xl bg-white text-black text-sm font-medium hover:bg-white/90 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Starting batch..." : "Start batch"}
          </button>
        </>
      ) : (
        <>
          {/* Progress header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-sm text-white/60">
                {allDone ? "Batch complete" : "Running batch"}
              </span>
              <span className="text-sm text-white/35">{doneCount} / {rows.length}</span>
            </div>
            <div className="flex items-center gap-2">
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
              <button
                onClick={handleReset}
                className="px-3 py-1.5 rounded-lg bg-white/8 text-white/60 hover:bg-white/14 hover:text-white text-sm transition-colors"
              >
                New batch
              </button>
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full h-1 bg-white/8 rounded-full overflow-hidden">
            <div
              className="h-full bg-white/60 rounded-full transition-all duration-500"
              style={{ width: `${progress * 100}%` }}
            />
          </div>

          {/* Task table */}
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
                    <td className="px-4 py-2.5 text-white/50 font-mono text-xs">{row.name}</td>
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
        </>
      )}
    </div>
  );
}
