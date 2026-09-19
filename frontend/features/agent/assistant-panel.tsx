"use client";
import { MessageSquareText, FileSearch } from "lucide-react";
import { ChatPanel } from "@/features/chat/chat-panel";
import { AgentPanel } from "./agent-panel";

export type AssistantMode = "chat" | "prepare";
export function AssistantModes({ mode, agentEnabled, onChange }: { mode: AssistantMode; agentEnabled: boolean; onChange: (mode: AssistantMode) => void }) {
  return <div className="assistant-modes" role="tablist" aria-label="助手模式">
    <button id="chat-tab" type="button" role="tab" aria-selected={mode === "chat"} aria-controls="chat-view" onClick={() => onChange("chat")}><MessageSquareText size={15} />企业问答</button>
    {agentEnabled && <button id="prepare-tab" type="button" role="tab" aria-selected={mode === "prepare"} aria-controls="prepare-view" onClick={() => onChange("prepare")}><FileSearch size={15} />任务准备<span>Agent</span></button>}
  </div>;
}
type Props = { mode: AssistantMode; agentEnabled: boolean; externalQuestion?: { id: number; text: string } | null; onAnswerComplete?: () => void };
export function AssistantPanel({ mode, agentEnabled, ...props }: Props) {
  return <div className="assistant-panel">
    <div className="assistant-view" id="chat-view" role="tabpanel" aria-labelledby="chat-tab" hidden={mode !== "chat"}><ChatPanel {...props} /></div>
    {agentEnabled && <div className="assistant-view" id="prepare-view" role="tabpanel" aria-labelledby="prepare-tab" hidden={mode !== "prepare"}><AgentPanel onAnswerComplete={props.onAnswerComplete} /></div>}
  </div>;
}
