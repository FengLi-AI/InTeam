import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatStreamError, parseSseEvent, streamChat } from "@/lib/stream/sse";

afterEach(() => vi.unstubAllGlobals());

describe("SSE parser", () => {
  it("parses the stable InTeam stream events", () => {
    expect(parseSseEvent('data: {"type":"status","phase":"retrieving"}')).toEqual({
      type: "status",
      phase: "retrieving",
    });
    expect(parseSseEvent('data: {"type":"chunk","text":"你好"}')).toEqual({ type: "chunk", text: "你好" });
    expect(parseSseEvent('data: {"type":"replace","text":"替换"}')).toEqual({ type: "replace", text: "替换" });
    expect(parseSseEvent('event: message\ndata: {"type":"done","answer":"完成","sources":[]}')).toEqual({
      type: "done",
      answer: "完成",
      sources: [],
    });
  });

  it("ignores malformed or unknown events without breaking the stream", () => {
    expect(parseSseEvent("data: not-json")).toBeNull();
    expect(parseSseEvent('data: {"type":"ping"}')).toBeNull();
    expect(parseSseEvent("")).toBeNull();
  });

  it("completes only after a terminal done event", async () => {
    const encoder = new TextEncoder();
    const reader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: encoder.encode('data: {"type":"chunk","text":"你好"}\n\n') })
        .mockResolvedValueOnce({ done: false, value: encoder.encode('data: {"type":"done","answer":"你好"}\n\n') })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, body: { getReader: () => reader }, headers: new Headers() });
    vi.stubGlobal("fetch", fetchMock);
    const events: unknown[] = [];

    await expect(streamChat("你好", { requestId: "request123", onEvent: (event) => events.push(event) })).resolves.toBeUndefined();
    expect(events).toHaveLength(2);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({
      question: "你好",
      request_id: "request123",
    });
  });

  it("reports an interrupted stream and remembers whether partial text arrived", async () => {
    const encoder = new TextEncoder();
    const reader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: encoder.encode('data: {"type":"chunk","text":"部分回答"}\n\n') })
        .mockRejectedValueOnce(new TypeError("connection reset")),
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, body: { getReader: () => reader }, headers: new Headers() }));

    await expect(streamChat("问题", { onEvent: () => undefined })).rejects.toMatchObject({
      name: "ChatStreamError",
      code: "stream_interrupted",
      hasPartialAnswer: true,
    } satisfies Partial<ChatStreamError>);
  });

  it("treats an EOF without done or error as an incomplete stream", async () => {
    const reader = { read: vi.fn().mockResolvedValueOnce({ done: true, value: undefined }) };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, body: { getReader: () => reader }, headers: new Headers() }));

    await expect(streamChat("问题", { onEvent: () => undefined })).rejects.toMatchObject({
      code: "stream_incomplete",
      hasPartialAnswer: false,
    });
  });
});
