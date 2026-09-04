const configuredHosts = (
  process.env.NEXT_PUBLIC_ALLOWED_SOURCE_HOSTS || "feishu.cn,open.feishu.cn"
)
  .split(",")
  .map((host) => host.trim().toLowerCase())
  .filter(Boolean);

export function safeExternalUrl(value?: string): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return null;
    const host = url.hostname.toLowerCase();
    const allowed = configuredHosts.some(
      (candidate) => host === candidate || host.endsWith(`.${candidate}`),
    );
    return allowed ? url.toString() : null;
  } catch {
    return null;
  }
}
