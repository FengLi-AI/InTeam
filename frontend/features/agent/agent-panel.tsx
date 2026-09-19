"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, BookOpen, Check, ChevronDown, CircleAlert, Copy, FileSearch, History, LoaderCircle, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { GAP_LABELS, runPresentation } from "./presentation";
import { MessageComposer } from "@/features/chat/message-composer";
import { MarkdownMessage } from "@/features/chat/markdown-message";
import { getAgentConfig, getAgentRun, getAgentRuns, stopAgentRun, streamPreparation, type AgentRun, type Scenario } from "./api";

const EXAMPLES: Record<Scenario, string[]> = {
  exhibition: ["我是新讲解员，明天接待中学生，帮我准备青禾能源探索馆的 10 分钟讲解。", "我第一次带观众体验风能互动台，需要提前准备什么？", "青禾能源探索馆今年实际发了多少电？请帮我核实后准备回答。"],
  company: ["我是新入职的 AI 产品经理，帮我准备第一次参与北辰计划需求评审。", "根据岗位目标，帮我整理第一周的学习与准备清单。", "帮我梳理北辰计划的主要风险和需要进一步确认的问题。"],
};
const EXAMPLE_LABELS: Record<Scenario, string[]> = {
  exhibition: ["准备 10 分钟中学生讲解", "第一次操作风能互动台", "核实展厅年度发电量"],
  company: ["准备第一次项目需求评审", "整理第一周上手清单", "梳理项目风险与待确认事项"],
};


export function AgentPanel({ onAnswerComplete }: { onAnswerComplete?: () => void }) {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["agent-config"], queryFn: getAgentConfig, retry: false });
  const history = useQuery({ queryKey: ["agent-runs"], queryFn: getAgentRuns, refetchInterval: (query) => query.state.data?.items.some((item) => item.status === "running") ? 1000 : false });
  const [scenario, setScenario] = useState<Scenario>("exhibition");
  const [input, setInput] = useState("");
  const [active, setActive] = useState<AgentRun | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [stopping, setStopping] = useState(false);
  const [copied, setCopied] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const historyRef = useRef<HTMLDetailsElement>(null);
  const submitRef = useRef(false);
  const selected = active ?? history.data?.items.find((item) => item.id === selectedId) ?? null;
  const running = active?.status === "running";
  const presentation = selected ? runPresentation(selected) : null;
  const records = history.data?.items.filter((item) => item.scenario === scenario) ?? [];

  useEffect(() => () => { controllerRef.current?.abort(); }, []);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = running ? scrollRef.current.scrollHeight : 0;
  }, [active?.events.length, running]);

  function fresh(nextScenario = scenario) {
    setScenario(nextScenario); setActive(null); setSelectedId(null); setError(""); setInput(""); setCopied(false);
    if (historyRef.current) historyRef.current.open = false;
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }

  async function start(question = input) {
    const value = question.trim();
    if (!value || submitRef.current || !config.data?.ready) return;
    submitRef.current = true;
    const controller = new AbortController();
    controllerRef.current = controller;
    runIdRef.current = null;
    setError(""); setInput(""); setCopied(false);
    if (historyRef.current) historyRef.current.open = false;
    const parent = selected && ["completed", "limited", "needs_input"].includes(selected.status) ? selected.id : undefined;
    setActive({ id: "", question: value, scenario, status: "running", events: [], result: {}, parent_run_id: parent });
    try {
      await streamPreparation(value, scenario, parent, controller.signal, (event) => {
        if (event.type === "started") {
          runIdRef.current = event.run_id;
          setActive((current) => current ? { ...current, id: event.run_id } : current);
        } else if (event.type === "trace") {
          setActive((current) => current ? { ...current, events: [...current.events, event.event] } : current);
        } else if (event.type === "done") {
          setActive((current) => current ? { ...current, id: event.run_id, status: event.status, result: event.result } : current);
          onAnswerComplete?.();
        }
      });
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : "连接中断，请重试。");
        setInput(value);
        // A stream may disconnect after the server committed a result. Recover its real state.
        let recovered = false;
        if (runIdRef.current) {
          try {
            const run = await getAgentRun(runIdRef.current);
            if (run.status !== "running") {
              setActive(run); setError(""); recovered = true;
              if (["completed", "limited", "needs_input"].includes(run.status)) setInput("");
              onAnswerComplete?.();
            }
          } catch { /* The error banner already explains the interruption. */ }
        }
        if (!recovered) setActive((current) => current ? { ...current, status: "interrupted" } : current);
      }
    } finally {
      controllerRef.current = null; submitRef.current = false; setStopping(false);
      void queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
    }
  }

  async function stop() {
    if (!runIdRef.current || stopping) return;
    setStopping(true);
    try { await stopAgentRun(runIdRef.current); }
    catch { setError("停止请求未成功，任务仍在运行，请再试一次。"); setStopping(false); }
  }

  async function copy() {
    if (!selected?.result.answer) return;
    const sources = selected.result.sources?.map((s) => `- ${s.title}`).join("\n") ?? "";
    const gaps = presentation?.gaps.map((gap) => `- ${gap.kind === "unclassified" ? "待补充或核实" : GAP_LABELS[gap.kind]}：${gap.text}`).join("\n") ?? "";
    const sections = [selected.result.title, selected.result.answer, gaps ? `待补充与核实\n${gaps}` : "", sources ? `参考资料\n${sources}` : ""].filter(Boolean);
    try { await navigator.clipboard.writeText(sections.join("\n\n")); setCopied(true); }
    catch { setError("复制未成功，请选中正文手动复制。"); }
  }

  return (
    <section className="preparation-panel" aria-label="任务准备">
      <div className="prep-toolbar">
        <div className="prep-scenarios" aria-label="准备场景">
          <button type="button" aria-pressed={scenario === "exhibition"} disabled={running} onClick={() => fresh("exhibition")}>展厅讲解</button>
          <button type="button" aria-pressed={scenario === "company"} disabled={running} onClick={() => fresh("company")}>企业上手</button>
        </div>
        <div className="prep-toolbar-actions">
          {!!records.length && !running && <details className="prep-history" ref={historyRef} onKeyDown={(event) => { if (event.key === "Escape") { event.currentTarget.open = false; event.currentTarget.querySelector("summary")?.focus(); } }} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false; }}>
            <summary><History size={14} /><span>最近记录</span><ChevronDown size={12} /></summary>
            <div className="prep-history-list" aria-label="最近准备记录">{records.map((run) => <button type="button" key={run.id} onClick={() => { setActive(null); setSelectedId(run.id); setError(""); setInput(""); setCopied(false); if (historyRef.current) historyRef.current.open = false; if (scrollRef.current) scrollRef.current.scrollTop = 0; }}><span>{run.question}</span><small>{runPresentation(run).label}</small></button>)}</div>
          </details>}
          <button className="prep-new" type="button" disabled={running} onClick={() => fresh()}><Plus size={14} />新任务</button>
        </div>
      </div>
      <div className={`prep-scroll scroll-area${!selected ? " is-empty" : ""}`} ref={scrollRef}>
        {!selected && <div className="prep-empty">
          <div className="prep-intro"><span className="prep-symbol"><FileSearch size={23} strokeWidth={1.5} /></span><h2>{scenario === "exhibition" ? "准备好你的下一场讲解" : "从了解业务，到开始工作"}</h2></div>
          <p>说说任务、对象和要求，我来查资料、整理准备材料。</p>
          <div className="prep-examples">{EXAMPLES[scenario].map((text, index) => <button key={text} type="button" title={text} disabled={!config.data?.ready} onClick={() => void start(text)}><span>{EXAMPLE_LABELS[scenario][index]}</span><ArrowUp size={15} /></button>)}</div>
          <div className="prep-scope"><BookOpen size={14} /><span>{scenario === "exhibition" ? "可查阅展厅主线、展项知识、操作须知及培训资料" : "可查阅公司制度、岗位协作与北辰计划资料"}</span></div>
        </div>}
        {selected && <div className="prep-task">
          <div className="prep-request"><span>{selected.parent_run_id ? "继续准备" : "本次任务"}</span><p>{selected.question}</p></div>
          <div className={`prep-status is-${selected.status}`} role="status">{running ? <LoaderCircle size={15} className="spin" /> : presentation?.materialReady ? <Check size={15} /> : <CircleAlert size={15} />}{presentation?.label}{presentation?.supplement && <button type="button" className="prep-gap-link" onClick={() => document.getElementById("prep-information-gaps")?.scrollIntoView({ block: "nearest", behavior: "smooth" })}>{presentation.supplement}<ChevronDown size={12} /></button>}</div>
          {selected.events.length > 0 && <details className="prep-trace" open={running || undefined}>
            <summary><FileSearch size={14} />查看准备过程<span>{selected.events.filter((e) => e.kind === "tool_start").length} 次资料查询</span><ChevronDown size={14} /></summary>
            <ol>{selected.events.filter((event) => event.kind !== "model" || running).map((event) => <li key={event.seq}>
              <span className="trace-dot" /><div><b>{event.kind === "finished" ? presentation?.label : event.label}</b>{event.arguments && <p>{event.arguments.query ?? event.arguments.document_id}</p>}<small>{(event.elapsed_ms / 1000).toFixed(1)} 秒{event.tool ? ` · ${event.tool}` : ""}</small></div>
            </li>)}</ol>
          </details>}
          {selected.result.answer && <article className="prep-result">
            <div className="prep-result-title"><h3>{selected.result.title}</h3><button type="button" onClick={() => void copy()} aria-label="复制准备材料">{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "已复制" : "复制"}</button></div>
            <MarkdownMessage>{selected.result.answer}</MarkdownMessage>
            {!!presentation?.gaps.length && <div className="prep-missing" id="prep-information-gaps">{(["task_input", "source_gap", "live_check", "unclassified"] as const).map((kind) => {
              const items = presentation.gaps.filter((gap) => gap.kind === kind);
              return items.length ? <section key={kind}><b>{kind === "unclassified" ? "待补充或核实" : GAP_LABELS[kind]}</b><ul>{items.map((gap, i) => <li key={i}>{gap.text}</li>)}</ul></section> : null;
            })}</div>}
            {!!selected.result.sources?.length && <details className="prep-sources"><summary><BookOpen size={14} />参考了 {selected.result.sources.length} 份资料</summary>{selected.result.sources.map((source) => <div key={source.document_id}><b>{source.title}</b><p>{source.excerpt}</p></div>)}</details>}
            {!!selected.result.action_suggestions?.length && <p className="prep-action-notice"><Check size={14} />已整理 {selected.result.action_suggestions.length} 条可选行动，请在“入职推进”或“我的计划”中确认。</p>}
          </article>}
          {selected.result.message && <p className="prep-notice">{selected.result.message}</p>}
        </div>}
      </div>
      <div className="prep-composer-area">
        {(error || config.isError || (config.data && !config.data.ready)) && <p role="alert" className="prep-error">{error || (config.isError ? "暂时无法连接任务准备服务，请刷新后重试。" : config.data?.message)}</p>}
        <MessageComposer id="preparation-input" value={input} onChange={setInput} onSubmit={() => void start()} onStop={() => void stop()} busy={Boolean(running)} stopping={stopping} disabled={!config.data?.ready} stopDisabled={!active?.id} lockWhileBusy maxLength={3000} variant="prepare" label={selected && ["completed", "limited", "needs_input"].includes(selected.status) ? "补充要求，继续这次准备" : "这次想准备什么？"} sendLabel="开始准备" stopLabel="停止准备" examples={EXAMPLES[scenario]} />
      </div>
    </section>
  );
}
