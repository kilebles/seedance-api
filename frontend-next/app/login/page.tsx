"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { setAuthToken, encodeCredentials } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function LoginPage() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const token = encodeCredentials(username, password);
    try {
      const res = await fetch(`${API_BASE}/generations/tasks`, {
        headers: { Authorization: `Basic ${token}` },
      });
      if (res.status === 401) {
        setError("Неверный логин или пароль");
        return;
      }
      if (!res.ok) {
        setError(`Ошибка сервера: ${res.status}`);
        return;
      }
      setAuthToken(token);
      router.replace("/");
    } catch {
      setError("Не удалось подключиться к серверу");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 text-white">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 p-6 rounded-xl bg-white/5 border border-white/8">
        <h1 className="text-lg font-medium">Вход</h1>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Логин"
          autoComplete="username"
          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/25 outline-none focus:border-white/25"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Пароль"
          autoComplete="current-password"
          autoFocus
          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/25 outline-none focus:border-white/25"
        />
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={loading || !password}
          className="w-full py-2 rounded-lg bg-white text-zinc-900 font-medium disabled:opacity-40 transition-opacity"
        >
          {loading ? "..." : "Войти"}
        </button>
      </form>
    </div>
  );
}
