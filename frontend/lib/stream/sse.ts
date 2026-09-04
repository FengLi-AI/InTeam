import { ApiError, apiUrl } from "@/lib/api/client";
import type { ChatStreamEvent } from "@/lib/api/types";

type StreamChatOptions = {
  signal?: AbortSignal;
  requestId?: string;
  onEvent: (event: ChatStreamEvent) => void;
};

export class ChatStreamError extends Error {
  constructor(
    readonly code: "stream_interrupted" | "stream_incomplete",
    readonly hasPartialAnswer: boolean,
  ) {
    super(code === "stream_interrupted" ? "聊天连接中断" : "聊天响应未完整结束");
    this.name = "ChatStreamError";
  }
}

export function parseSseEvent(raw: string): ChatStreamEvent | null {
  const data = raw
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;

  try {
    const event = JSON.parse(data) as unknown;
    if (!event || typeof event !== "object" || !("type" in event)) return null;
    const type = (event as { type?: unknown }).type;
    if (["status", "chunk", "replace", "done", "error"].includes(String(type))) {
      return event as ChatStreamEvent;
    }
    return null;
  } catch {
    return null;
  }
}

export async function streamChat(question: string, options: StreamChatOptions) {
  const response = await fetch(apiUrl("/chat"), {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      question,
      session_id: "web",
      request_id: options.requestId ?? crypto.randomUUID().replaceAll("-", ""),
    }),
    signal: options.signal,
  });

  if (!response.ok || !response.body) {
    throw new ApiError(
      response.status === 429 ? "请求较多，请稍后再试" : `问答请求失败（${response.status}）`,
      response.status,
      response.headers.get("Retry-After") ?? undefined,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let hasPartialAnswer = false;
  let hasTerminalEvent = false;

  const emit = (event: ChatStreamEvent | null) => {
    if (!event) return;
    if ((event.type === "chunk" || event.type === "replace") && event.text) hasPartialAnswer = true;
    if (event.type === "done" || event.type === "error") hasTerminalEvent = true;
    options.onEvent(event);
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        emit(parseSseEvent(buffer.slice(0, boundary).trim()));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }

      if (done) break;
    }
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ChatStreamError("stream_interrupted", hasPartialAnswer);
  }

  emit(parseSseEvent(buffer.trim()));
  if (!hasTerminalEvent) throw new ChatStreamError("stream_incomplete", hasPartialAnswer);
}
