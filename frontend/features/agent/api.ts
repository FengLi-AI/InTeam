import { apiRequest, apiUrl, jsonRequest } from "@/lib/api/client";
import type { AgentSuggestion } from "@/lib/api/types";

export type Scenario = "company" | "exhibition";
export type TraceEvent = { seq: number; kind: string; label: string; elapsed_ms: number; tool?: string; arguments?: { query?: string; document_id?: string }; status?: string; document_ids?: string[] };
export type InformationGap = { kind: "task_input" | "source_gap" | "live_check" | "unclassified"; text: string };
export type PreparationResult = {
  information_gaps?: InformationGap[];
  title?: string; answer?: string; message?: string; missing_information?: string[];
  sources?: { document_id: string; title: string; excerpt: string }[];
  action_suggestions?: AgentSuggestion[]; tool_calls?: number; rounds?: number; elapsed_ms?: number;
};
export type AgentRun = { id: string; question: string; scenario: Scenario; parent_run_id?: string; status: string; events: TraceEvent[]; result: PreparationResult; model?: string; created_at?: string };
export type AgentEvent =
  | { type: "started"; run_id: string }
  | { type: "trace"; event: TraceEvent }
  | { type: "done"; run_id: string; status: string; result: PreparationResult };

export const getAgentConfig = () => apiRequest<{ enabled: boolean; ready: boolean; message: string }>("/agent/config");
export const getAgentRuns = () => apiRequest<{ items: AgentRun[] }>("/agent/runs");
export const getAgentRun = (id: string) => apiRequest<AgentRun>(`/agent/runs/${id}`);
export const stopAgentRun = (id: string) => apiRequest<{ status: string }>(`/agent/runs/${id}/stop`, jsonRequest("POST", {}));

export async function streamPreparation(
  question: string, scenario: Scenario, parentRunId: string | undefined,
  signal: AbortSignal, onEvent: (event: AgentEvent) => void,
) {
  const response = await fetch(apiUrl("/agent/runs"), { ...jsonRequest("POST", { question, scenario, parent_run_id: parentRunId }), headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, credentials: "same-origin", signal });
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(typeof payload.detail === "string" ? payload.detail : `任务暂时不可用（${response.status}）`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  const emit = (frame: string) => {
    const data = frame.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trimStart()).join("\n");
    if (!data) return;
    const event = JSON.parse(data) as AgentEvent;
    if (event.type === "done") finished = true;
    if (["started", "trace", "done"].includes(event.type)) onEvent(event);
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        emit(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    if (buffer.trim()) emit(buffer);
    if (!finished) throw new Error("连接中断，任务没有完整返回。请查看最近记录或重新准备。");
  } finally {
    reader.releaseLock();
  }
}
