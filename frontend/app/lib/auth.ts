const TOKEN_KEY = "inteam_token";

export function getLegacyToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function clearLegacyToken() {
  localStorage.removeItem(TOKEN_KEY);
}
