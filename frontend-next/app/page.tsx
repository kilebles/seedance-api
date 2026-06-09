"use client";

import { useState } from "react";
import { Task, GenerationRequest, submitTask } from "@/lib/api";
import GenerateInput from "@/components/GenerateInput";
import TaskCard from "@/components/TaskCard";
import { useLocalStorage } from "@/lib/useLocalStorage";

export default function Home() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  function handleUpdate(updated: Task) {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col">
      {/* Results grid */}
      <main className="flex-1 overflow-y-auto px-6 py-6">
        {tasks.length === 0 && !loading && (
          <div className="h-full min-h-[60vh] flex items-center justify-center">
            <p className="text-white/15 text-base">Generate your first video below</p>
          </div>
        )}
        {tasks.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
            {tasks.map((t) => (
              <TaskCard key={t.id} task={t} onUpdate={handleUpdate} />
            ))}
          </div>
        )}
      </main>

      {/* Bottom input */}
      <div className="shrink-0 px-6 pb-6 pt-3">
        {error && <p className="text-red-400 text-sm mb-2 text-center">{error}</p>}
        <GenerateInput
          onSubmit={handleSubmit}
          loading={loading}
          ratio={ratio} setRatio={setRatio}
          resolution={resolution} setResolution={setResolution}
          duration={duration} setDuration={setDuration}
          generateAudio={generateAudio} setGenerateAudio={setGenerateAudio}
          seed={seed} setSeed={setSeed}
          upscaleResolution={upscaleResolution} setUpscaleResolution={setUpscaleResolution}
        />
      </div>
    </div>
  );
}
