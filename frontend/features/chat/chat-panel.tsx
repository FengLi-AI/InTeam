"use client";

import { ArrowUp, Bot, CheckCircle2, RotateCcw, ThumbsDown, ThumbsUp } from "lucide-react";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";

import { FoldText, ShinyText } from "@/features/effects/motion-primitives";
import { useScrollAffordance } from "@/features/workspace/use-scroll-affordance";
import { ApiError } from "@/lib/api/client";
import type { ChatDoneEvent, Message } from "@/lib/api/types";
import { sendFeedback, stopChat } from "@/lib/api/workspace";
import { ChatStreamError, streamChat } from "@/lib/stream/sse";

import { MarkdownMessage } from "./markdown-message";
import { MessageComposer } from "./message-composer";

type ChatPanelProps = {
  externalQuestion?: { id: number; text: string } | null;
  onAnswerComplete?: () => void;
};

const STARTERS = ["我入职第一周应该优先完成什么？", "AI 产品经理的 30 天目标是什么？", "北辰计划现在处于什么阶段？", "报销和权限申请分别用哪个系统？"];

const PHASES: Record<string, { label: string; progress: number }> = {
  connecting: { label: "正在绞尽脑汁", progress: 18 },
  accepted: { label: "正在理解你的问题", progress: 34 },
  retrieving: { label: "正在翻阅企业知识库", progress: 58 },
  generating: { label: "正在梳理回复", progress: 78 },
  streaming: { label: "正在组织成清晰答案", progress: 92 },
};

export function ChatPanel({ externalQuestion, onAnswerComplete }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [phase, setPhase] = useState("connecting");
  const [noteDraft, setNoteDraft] = useState("");
  const scroll = useScrollAffordance();
  const scrollRef = scroll.ref;
  const bottomRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const abortRef = useRef<AbortController | null>(null);
  const activeRequestIdRef = useRef<string | null>(null);
  const activeAssistantIndexRef = useRef<number | null>(null);
  const askRef = useRef<((question: string) => Promise<void>) | null>(null);
  const lastExternalQuestion = useRef(0);
  const playbackTimerRef = useRef<number | null>(null);
  const playbackQueueRef = useRef("");
  const playbackIndexRef = useRef<number | null>(null);
  const renderedTextRef = useRef("");
  const playbackWaitersRef = useRef<Array<() => void>>([]);
  useEffect(() => () => {
    abortRef.current?.abort();
    if (playbackTimerRef.current) window.clearTimeout(playbackTimerRef.current);
  }, []);

  useEffect(() => {
    if (stickToBottom.current) bottomRef.current?.scrollIntoView({ behavior: loading ? "auto" : "smooth", block: "end" });
  }, [messages, loading]);

  useEffect(() => {
    if (!externalQuestion || externalQuestion.id === lastExternalQuestion.current) return;
    lastExternalQuestion.current = externalQuestion.id;
    void askRef.current?.(externalQuestion.text);
  }, [externalQuestion]);

  function updateMessage(index: number, updater: (message: Message) => Message) {
    setMessages((current) => current.map((message, messageIndex) => messageIndex === index ? updater(message) : message));
  }

  function resolvePlaybackWaiters() {
    playbackWaitersRef.current.splice(0).forEach((resolve) => resolve());
  }

  function pumpPlayback() {
    const index = playbackIndexRef.current;
    if (index === null || playbackQueueRef.current.length === 0) {
      playbackTimerRef.current = null;
      resolvePlaybackWaiters();
      return;
    }
    const backlog = playbackQueueRef.current.length;
    const size = backlog > 1200 ? 42 : backlog > 500 ? 22 : backlog > 180 ? 10 : backlog > 60 ? 4 : 2;
    const piece = playbackQueueRef.current.slice(0, size);
    playbackQueueRef.current = playbackQueueRef.current.slice(size);
    renderedTextRef.current += piece;
    updateMessage(index, (message) => ({ ...message, content: renderedTextRef.current }));
    playbackTimerRef.current = window.setTimeout(pumpPlayback, 16);
  }

  function queuePlayback(index: number, text: string, replace = false) {
    playbackIndexRef.current = index;
    if (replace) {
      if (text.startsWith(renderedTextRef.current)) playbackQueueRef.current = text.slice(renderedTextRef.current.length);
      else {
        renderedTextRef.current = "";
        playbackQueueRef.current = text;
        updateMessage(index, (message) => ({ ...message, content: "" }));
      }
    } else playbackQueueRef.current += text;
    if (!playbackTimerRef.current) pumpPlayback();
  }

  function waitForPlayback() {
    if (!playbackTimerRef.current && playbackQueueRef.current.length === 0) return Promise.resolve();
    return new Promise<void>((resolve) => playbackWaitersRef.current.push(resolve));
  }

  function clearPlayback() {
    if (playbackTimerRef.current) window.clearTimeout(playbackTimerRef.current);
    playbackTimerRef.current = null;
    playbackQueueRef.current = "";
    playbackIndexRef.current = null;
    resolvePlaybackWaiters();
  }

  async function ask(question: string) {
    const value = question.trim();
    if (!value || loading) return;
    const assistantIndex = messages.length + 1;
    const requestId = crypto.randomUUID().replaceAll("-", "");
    setInput("");
    renderedTextRef.current = "";
    playbackQueueRef.current = "";
    setMessages((current) => [...current, { role: "user", content: value }, { role: "assistant", content: "", sources: [] }]);
    setLoading(true);
    setPhase("connecting");
    stickToBottom.current = true;
    const controller = new AbortController();
    abortRef.current = controller;
    activeRequestIdRef.current = requestId;
    activeAssistantIndexRef.current = assistantIndex;

    let doneEvent: ChatDoneEvent | null = null;
    try {
      await streamChat(value, {
        signal: controller.signal,
        requestId,
        onEvent: (event) => {
          if (event.type === "status") {
            setPhase(event.phase);
          } else if (event.type === "chunk") {
            setPhase("streaming");
            queuePlayback(assistantIndex, event.text);
          } else if (event.type === "replace") {
            setPhase("streaming");
            queuePlayback(assistantIndex, event.text, true);
          } else if (event.type === "done") {
            doneEvent = event;
            if (event.answer) queuePlayback(assistantIndex, event.answer, true);
          } else if (event.type === "error") {
            updateMessage(assistantIndex, (message) => ({
              ...message,
              content: `${message.content}\n\n[回答失败] ${event.error?.message ?? "请稍后重试"}`,
              retryQuestion: event.retryable === false ? undefined : value,
            }));
          }
        },
      });
      await waitForPlayback();
      if (doneEvent) {
        const completeEvent: ChatDoneEvent = doneEvent;
        updateMessage(assistantIndex, (message) => ({
          ...message,
          content: completeEvent.answer || message.content,
          retryQuestion: undefined,
          sources: [],
          guard: completeEvent.guard,
          answerId: completeEvent.answer_id,
          suggestedQuestions: completeEvent.suggested_questions ?? [],
          actionSuggestions: completeEvent.action_suggestions ?? [],
        }));
        onAnswerComplete?.();
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 429) {
        setInput(value);
        updateMessage(assistantIndex, (message) => ({
          ...message,
          content: `请求较多，请在 ${error.retryAfter ?? "几"} 秒后重试。你的问题已保留。`,
          retryQuestion: value,
        }));
      } else if (error instanceof ChatStreamError) {
        const notice = error.hasPartialAnswer
          ? "[连接中断] 上面的回答没有完整结束，请重新发送。"
          : "[连接中断] 本次回答未能完整返回，请重新发送。";
        updateMessage(assistantIndex, (message) => ({
          ...message,
          content: `${message.content}${message.content ? "\n\n" : ""}${notice}`,
          retryQuestion: value,
        }));
      } else if (error instanceof ApiError) {
        updateMessage(assistantIndex, (message) => ({
          ...message,
          content: `[服务暂时不可用] 请求返回 ${error.status}，请稍后重试。`,
          retryQuestion: error.status >= 500 ? value : undefined,
        }));
      } else {
        updateMessage(assistantIndex, (message) => ({
          ...message,
          content: `${message.content}${message.content ? "\n\n" : ""}[网络连接中断] 请检查网络后重新发送。`,
          retryQuestion: value,
        }));
      }
    } finally {
      if (abortRef.current === controller) {
        clearPlayback();
        setLoading(false);
        abortRef.current = null;
        activeRequestIdRef.current = null;
        activeAssistantIndexRef.current = null;
      }
    }
  }

  askRef.current = ask;

  async function stopGenerating() {
    const requestId = activeRequestIdRef.current;
    const controller = abortRef.current;
    const assistantIndex = activeAssistantIndexRef.current;
    if (!requestId || !controller || assistantIndex === null || stopping) return;
    setStopping(true);
    try {
      await stopChat(requestId);
      controller.abort();
      clearPlayback();
      updateMessage(assistantIndex, (message) => ({
        ...message,
        content: `${message.content}${message.content ? "\n\n" : ""}[已停止生成] 已保留上方内容。`,
        retryQuestion: undefined,
      }));
    } catch {
      updateMessage(assistantIndex, (message) => ({
        ...message,
        content: `${message.content}${message.content ? "\n\n" : ""}[停止失败] 当前回答仍在生成，可稍后重试。`,
      }));
    } finally {
      setStopping(false);
    }
  }

  async function feedback(index: number, answerId: string, helpful: boolean, note = "") {
    try {
      await sendFeedback(answerId, helpful, note);
      updateMessage(index, (message) => ({ ...message, feedback: helpful, askingNote: false }));
      setNoteDraft("");
    } catch {
      updateMessage(index, (message) => ({ ...message, content: `${message.content}\n\n[反馈提交失败] 请稍后重试。` }));
    }
  }

  const phaseData = PHASES[phase] ?? PHASES.generating;

  return (
    <section className="chat-panel" aria-label="AI 入职助手">
      <div
        className={`chat-scroll scroll-area center-scroll ${scroll.className}`}
        ref={scrollRef}
        onScroll={() => {
          scroll.onScroll();
          const element = scrollRef.current;
          if (!element) return;
          stickToBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        }}
      >
        {messages.length === 0 && (
          <div className="chat-empty">
            <Image className="agent-orb" src="/visuals/inteam-agent-orb.png" alt="InTeam AI Agent" width={320} height={320} priority unoptimized />
            <h2><ShinyText className="chat-greeting-shine" duration={4.8}><FoldText>今天想了解点什么？</FoldText></ShinyText></h2>
            <p>我会优先依据公司知识库回答，资料不足时会明确告诉你。</p>
            <div className="starter-grid">
              {STARTERS.map((starter) => <button key={starter} type="button" onClick={() => ask(starter)}>{starter}<ArrowUp size={14} /></button>)}
            </div>
          </div>
        )}

        <div className="message-list">
          {messages.map((message, index) => (
            <article className={`message-row ${message.role}`} key={`${message.role}-${index}`}>
              {message.role === "assistant" && <span className="message-avatar"><Bot size={17} /></span>}
              <div className="message-bubble">
                {message.role === "assistant" && message.content
                  ? <MarkdownMessage>{message.content}</MarkdownMessage>
                  : <div className="message-copy">{message.content || (loading && index === messages.length - 1 ? <div className="thinking-stage" aria-live="polite"><span><i />{phaseData.label}</span><div><b style={{ width: `${phaseData.progress}%` }} /></div></div> : "")}</div>}

                {message.role === "assistant" && message.retryQuestion && (
                  <div className="retry-actions">
                    <button type="button" disabled={loading} onClick={() => ask(message.retryQuestion!)} aria-label={`重新发送：${message.retryQuestion}`}>
                      <RotateCcw size={13} />重新发送
                    </button>
                  </div>
                )}

                {message.role === "assistant" && message.suggestedQuestions && message.suggestedQuestions.length > 0 && (
                  <div className="suggested-questions">{message.suggestedQuestions.map((question) => <button type="button" key={question} onClick={() => ask(question)}>{question}</button>)}</div>
                )}

                {message.role === "assistant" && message.actionSuggestions && message.actionSuggestions.length > 0 && (
                  <div className="message-suggestion-notice"><CheckCircle2 size={14} />已生成 {message.actionSuggestions.length} 条候选行动，可在“入职推进”中确认。</div>
                )}

                {message.role === "assistant" && message.answerId && (
                  <div className="answer-actions">
                    {message.askingNote ? (
                      <div className="feedback-note">
                        <input value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="可选：哪里没帮到你？" aria-label="反馈说明" />
                        <button type="button" onClick={() => feedback(index, message.answerId!, false, noteDraft)}>提交</button>
                        <button type="button" onClick={() => updateMessage(index, (current) => ({ ...current, askingNote: false }))}>取消</button>
                      </div>
                    ) : message.feedback === undefined ? (
                      <>
                        <span>有帮助吗？</span>
                        <button type="button" onClick={() => feedback(index, message.answerId!, true)}><ThumbsUp size={13} />有帮助</button>
                        <button type="button" onClick={() => updateMessage(index, (current) => ({ ...current, askingNote: true }))}><ThumbsDown size={13} />没解决</button>
                      </>
                    ) : (
                      <span>{message.feedback ? "已反馈：有帮助" : "已反馈：没解决"}</span>
                    )}
                  </div>
                )}
              </div>
            </article>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <MessageComposer value={input} onChange={setInput} onSubmit={() => void ask(input)} onStop={() => void stopGenerating()} busy={loading} stopping={stopping} label="向入职助手提问" sendLabel="发送问题" stopLabel="停止生成" examples={STARTERS} />
    </section>
  );
}
