"use client";

import { useRef, useState } from "react";
import { ChevronDown, ImagePlus, ArrowUp, X, Settings2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toDataUri, GenerationRequest, ContentItem } from "@/lib/api";
import Settings from "@/components/Settings";

export type ImageRole = "first_frame" | "last_frame" | "reference_image";
export type VideoRole = "reference_video";
export type Mode = "default" | "first_frame" | "last_frame" | "first_last" | "v2v";

const MODE_LABELS: Record<Mode, string> = {
  default: "Default",
  first_frame: "First frame",
  last_frame: "Last frame",
  first_last: "First + Last",
  v2v: "V2V",
};

const MAX_REFS = 4;

type SlotKind = "image" | "video";
interface Slot { role: ImageRole | VideoRole; label: string; kind: SlotKind }

interface Props {
  onSubmit: (req: GenerationRequest) => void;
  loading: boolean;
  ratio: string; setRatio: (v: string) => void;
  resolution: string; setResolution: (v: string) => void;
  duration: number; setDuration: (v: number) => void;
  generateAudio: boolean; setGenerateAudio: (v: boolean) => void;
  seed: number | null; setSeed: (v: number | null) => void;
  upscaleResolution: string | null; setUpscaleResolution: (v: string | null) => void;
}

export default function GenerateInput({
  onSubmit, loading,
  ratio, setRatio, resolution, setResolution,
  duration, setDuration, generateAudio, setGenerateAudio,
  seed, setSeed, upscaleResolution, setUpscaleResolution,
}: Props) {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<Mode>("default");
  // default mode: list of reference images (up to MAX_REFS)
  const [refImages, setRefImages] = useState<File[]>([]);
  // fixed-slot modes: keyed by role
  const [slotFiles, setSlotFiles] = useState<Partial<Record<string, File>>>({});

  const imgInputRef = useRef<HTMLInputElement>(null);
  const vidInputRef = useRef<HTMLInputElement>(null);
  const [pendingSlot, setPendingSlot] = useState<Slot | null>(null);

  // Fixed slots for non-default modes
  const fixedSlots: Slot[] = mode === "first_frame" ? [{ role: "first_frame", label: "First frame", kind: "image" }]
    : mode === "last_frame"  ? [{ role: "last_frame", label: "Last frame", kind: "image" }]
    : mode === "first_last"  ? [{ role: "first_frame", label: "First", kind: "image" }, { role: "last_frame", label: "Last", kind: "image" }]
    : mode === "v2v"         ? [{ role: "reference_video", label: "Video", kind: "video" }]
    : [];

  function openRefPicker() {
    setPendingSlot(null);
    imgInputRef.current?.click();
  }

  function openSlotPicker(slot: Slot) {
    setPendingSlot(slot);
    (slot.kind === "video" ? vidInputRef : imgInputRef).current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (pendingSlot) {
      setSlotFiles((prev) => ({ ...prev, [pendingSlot.role]: file }));
    } else {
      setRefImages((prev) => prev.length < MAX_REFS ? [...prev, file] : prev);
    }
    e.target.value = "";
  }

  function removeRef(idx: number) {
    setRefImages((prev) => prev.filter((_, i) => i !== idx));
  }

  function removeSlot(role: string) {
    setSlotFiles((prev) => { const n = { ...prev }; delete n[role]; return n; });
  }

  function changeMode(m: Mode) {
    setMode(m);
    setRefImages([]);
    setSlotFiles({});
  }

  async function handleSubmit() {
    if (loading || !prompt.trim()) return;

    const content: ContentItem[] = [];

    if (mode === "default") {
      for (const file of refImages) {
        content.push({ type: "image_url", image_url: { url: await toDataUri(file) }, role: "reference_image" });
      }
    } else {
      for (const slot of fixedSlots) {
        const file = slotFiles[slot.role];
        if (!file) continue;
        if (slot.kind === "image") {
          content.push({ type: "image_url", image_url: { url: await toDataUri(file) }, role: slot.role as ImageRole });
        } else {
          content.push({ type: "video_url", video_url: { url: await toDataUri(file) }, role: slot.role });
        }
      }
    }

    content.push({ type: "text", text: prompt.trim() });

    onSubmit({
      content, ratio, resolution, duration,
      generate_audio: generateAudio,
      ...(seed !== null ? { seed } : {}),
      ...(upscaleResolution ? { upscale_resolution: upscaleResolution } : {}),
    });
    setPrompt("");
    setRefImages([]);
    setSlotFiles({});
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  }

  function handlePaste(e: React.ClipboardEvent<HTMLTextAreaElement>) {
    const items = Array.from(e.clipboardData.items);
    const imageItems = items.filter((i) => i.type.startsWith("image/"));
    if (imageItems.length === 0) return;
    e.preventDefault();
    for (const item of imageItems) {
      const file = item.getAsFile();
      if (!file) continue;
      if (mode === "default") {
        setRefImages((prev) => prev.length < MAX_REFS ? [...prev, file] : prev);
      } else if (pendingSlot) {
        setSlotFiles((prev) => ({ ...prev, [pendingSlot.role]: file }));
      } else if (fixedSlots.length > 0) {
        // fill first empty slot
        const emptySlot = fixedSlots.find((s) => !slotFiles[s.role]);
        if (emptySlot) setSlotFiles((prev) => ({ ...prev, [emptySlot.role]: file }));
      }
    }
  }

  const canSubmit = !loading && !!prompt.trim();
  const showRefAdd = mode === "default" && refImages.length < MAX_REFS;

  // Whether we have any media to show inside the box
  const hasRefMedia = mode === "default" && refImages.length > 0;
  const hasFixedMedia = mode !== "default" && fixedSlots.length > 0;
  const showMediaRow = hasRefMedia || hasFixedMedia;

  return (
    <div className="w-full">
      <div className="bg-white/5 rounded-2xl px-3 pt-3 pb-2.5 flex flex-col gap-2">

        {/* Media row — inside the box */}
        {showMediaRow && (
          <div className="flex gap-2 flex-wrap">
            {mode === "default" ? (
              refImages.map((file, idx) => (
                <div key={idx} className="relative w-14 h-14 rounded-xl overflow-hidden shrink-0">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={URL.createObjectURL(file)} alt="" className="w-full h-full object-cover" />
                  <button onClick={() => removeRef(idx)} className="absolute top-0.5 right-0.5 bg-black/70 rounded-full p-0.5">
                    <X size={10} />
                  </button>
                </div>
              ))
            ) : (
              fixedSlots.map((slot) => {
                const file = slotFiles[slot.role];
                return (
                  <div key={slot.role} className="shrink-0">
                    {file ? (
                      <div className="relative w-14 h-14 rounded-xl overflow-hidden bg-white/5">
                        {slot.kind === "image" ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={URL.createObjectURL(file)} alt={slot.label} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-white/40 text-[10px] px-1 text-center">{file.name.slice(0, 12)}</div>
                        )}
                        <button onClick={() => removeSlot(slot.role)} className="absolute top-0.5 right-0.5 bg-black/70 rounded-full p-0.5">
                          <X size={10} />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => openSlotPicker(slot)}
                        className="w-14 h-14 rounded-xl border border-dashed border-white/15 flex flex-col items-center justify-center text-white/35 hover:border-white/30 hover:text-white/55 transition-colors gap-1"
                      >
                        <ImagePlus size={14} />
                        <span className="text-[10px]">{slot.label}</span>
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Fixed slots placeholder row — shown even before files added, so user sees what to fill */}
        {mode !== "default" && !hasFixedMedia && (
          <div className="flex gap-2">
            {fixedSlots.map((slot) => (
              <button
                key={slot.role}
                onClick={() => openSlotPicker(slot)}
                className="w-14 h-14 rounded-xl border border-dashed border-white/15 flex flex-col items-center justify-center text-white/35 hover:border-white/30 hover:text-white/55 transition-colors gap-1 shrink-0"
              >
                <ImagePlus size={14} />
                <span className="text-[10px]">{slot.label}</span>
              </button>
            ))}
          </div>
        )}

        {/* Prompt */}
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="Describe your video..."
          rows={3}
          className="w-full bg-transparent resize-none text-base text-white placeholder-white/25 outline-none leading-6 overflow-y-auto"
          style={{ scrollbarWidth: "none" }}
        />

        {/* Bottom controls row */}
        <div className="flex items-center gap-1">
          {/* + image button (default mode only) */}
          {mode === "default" && (
            <button
              onClick={openRefPicker}
              disabled={!showRefAdd}
              title="Add image"
              className="w-8 h-8 flex items-center justify-center rounded-full text-white/40 hover:text-white hover:bg-white/10 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
            >
              <ImagePlus size={17} />
            </button>
          )}

          {/* Mode dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-1 text-xs text-white/35 hover:text-white/65 transition-colors whitespace-nowrap bg-transparent border-none outline-none cursor-pointer px-1">
              {MODE_LABELS[mode]}
              <ChevronDown size={11} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="bg-zinc-900 border-white/10 text-white min-w-40">
              <DropdownMenuRadioGroup value={mode} onValueChange={(v) => changeMode(v as Mode)}>
                {(Object.keys(MODE_LABELS) as Mode[]).map((m) => (
                  <DropdownMenuRadioItem key={m} value={m} className="text-sm cursor-pointer">
                    {MODE_LABELS[m]}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>

          <div className="flex-1" />

          {/* Settings */}
          <Settings
            ratio={ratio} setRatio={setRatio}
            resolution={resolution} setResolution={setResolution}
            duration={duration} setDuration={setDuration}
            generateAudio={generateAudio} setGenerateAudio={setGenerateAudio}
            seed={seed} setSeed={setSeed}
            upscaleResolution={upscaleResolution} setUpscaleResolution={setUpscaleResolution}
          >
            <button className="w-8 h-8 flex items-center justify-center rounded-full text-white/35 hover:text-white hover:bg-white/10 transition-colors">
              <Settings2 size={16} />
            </button>
          </Settings>

          {/* Send */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="w-8 h-8 flex items-center justify-center rounded-full bg-white text-black hover:bg-white/90 disabled:opacity-25 disabled:cursor-not-allowed transition-all"
          >
            <ArrowUp size={16} />
          </button>
        </div>
      </div>

      <input ref={imgInputRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={handleFileChange} />
      <input ref={vidInputRef} type="file" accept="video/mp4,video/webm,video/quicktime" className="hidden" onChange={handleFileChange} />
    </div>
  );
}
