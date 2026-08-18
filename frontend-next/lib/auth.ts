const COOKIE_NAME = "seedance_auth";

export function getAuthToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE_NAME}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function setAuthToken(token: string): void {
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(token)}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
}

export function clearAuthToken(): void {
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0`;
  if (typeof window !== "undefined") window.location.href = "/login";
}

export function encodeCredentials(username: string, password: string): string {
  return btoa(`${username}:${password}`);
}

export function authHeader(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Basic ${token}` } : {};
}
