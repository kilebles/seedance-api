"use client";

import { useState } from "react";
import { X } from "lucide-react";

export type GenerateMode = "video" | "image";

interface Props {
  generateMode: GenerateMode; setGenerateMode: (v: GenerateMode) => void;
  ratio: string; setRatio: (v: string) => void;
  resolution: string; setResolution: (v: string) => void;
  duration: number; setDuration: (v: number) => void;
  generateAudio: boolean; setGenerateAudio: (v: boolean) => void;
  seed: number | null; setSeed: (v: number | null) => void;
  upscaleResolution: string | null; setUpscaleResolution: (v: string | null) => void;
  children: React.ReactNode;
}

const RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"];
const RESOLUTIONS = ["720p", "480p"];
const DURATIONS = [4,5,6,7,8,9,10,11,12,13,14,15];
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

export default function Settings({
  children,
  generateMode, setGenerateMode,
  ratio, setRatio, resolution, setResolution,
  duration, setDuration, generateAudio, setGenerateAudio,
  seed, setSeed, upscaleResolution, setUpscaleResolution,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <span onClick={() => setOpen(true)} className="cursor-pointer">{children}</span>

      {open && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)}>
          <div className="bg-zinc-900 rounded-2xl p-5 w-full max-w-sm space-y-5 m-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <span className="text-base font-medium text-white">Settings</span>
              <button onClick={() => setOpen(false)} className="text-white/35 hover:text-white"><X size={16} /></button>
            </div>

            {/* Mode switch */}
            <div>
              <p className="text-xs text-white/35 mb-2">Mode</p>
              <div className="flex gap-1.5">
                <Pill active={generateMode === "video"} onClick={() => setGenerateMode("video")}>Video</Pill>
                <Pill active={generateMode === "image"} onClick={() => setGenerateMode("image")}>Image</Pill>
              </div>
            </div>

            {/* Video-only settings */}
            {generateMode === "video" && (
              <>
                <div>
                  <p className="text-xs text-white/35 mb-2">Aspect ratio</p>
                  <div className="flex flex-wrap gap-1.5">
                    {RATIOS.map((r) => <Pill key={r} active={ratio === r} onClick={() => setRatio(r)}>{r}</Pill>)}
                  </div>
                </div>

                <div>
                  <p className="text-xs text-white/35 mb-2">Resolution</p>
                  <div className="flex gap-1.5">
                    {RESOLUTIONS.map((r) => <Pill key={r} active={resolution === r} onClick={() => setResolution(r)}>{r}</Pill>)}
                  </div>
                </div>

                <div>
                  <p className="text-xs text-white/35 mb-2">Duration</p>
                  <div className="flex flex-wrap gap-1.5">
                    {DURATIONS.map((d) => <Pill key={d} active={duration === d} onClick={() => setDuration(d)}>{d}s</Pill>)}
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <p className="text-sm text-white/55">Generate audio</p>
                  <Toggle on={generateAudio} onToggle={() => setGenerateAudio(!generateAudio)} />
                </div>

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
              </>
            )}

            {/* Shared: seed */}
            <div>
              <div className="flex items-center justify-between">
                <p className="text-sm text-white/55">Fixed seed</p>
                <Toggle on={seed !== null} onToggle={() => setSeed(seed !== null ? null : 0)} />
              </div>
              {seed !== null && (
                <input
                  type="number" value={seed} min={0} max={4294967295}
                  onChange={(e) => setSeed(Number(e.target.value))}
                  className="mt-2 w-full bg-white/5 rounded-xl px-3 py-2 text-sm text-white outline-none"
                />
              )}
            </div>

            <button
              onClick={() => setOpen(false)}
              className="w-full py-2.5 rounded-xl bg-white text-black text-sm font-medium hover:bg-white/90 transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </>
  );
}
