"use client";

import { CalendarDays, Check, ChevronDown, Circle, Clock3, ListChecks, LoaderCircle, Pencil, Save, Sparkles, Trash2, X } from "lucide-react";
import { useState } from "react";

import { useScrollAffordance } from "@/features/workspace/use-scroll-affordance";
import type { ActionItem, ActionPlan, AgentSuggestion } from "@/lib/api/types";

type ActionPlanPanelProps = {
  plan?: ActionPlan;
  loading: boolean;
  error: boolean;
  busy: boolean;
  onAccept: (suggestion: AgentSuggestion) => void;
  onDismiss: (suggestion: AgentSuggestion) => void;
  onToggle: (action: ActionItem) => void;
  onUpdate: (action: ActionItem, patch: Pick<ActionItem, "title" | "due_date">) => void;
  onDelete: (action: ActionItem) => void;
};

const DUE_LABELS: Record<AgentSuggestion["due_hint"], string> = {
  today: "建议今天",
  within_3_days: "建议 3 天内",
  this_week: "建议本周",
  no_date: "暂不设日期",
};

const TOPIC_LABELS: Record<string, string> = {
  today_start: "今日开始",
  company_business: "公司与业务",
  my_role: "我的岗位",
  current_project: "当前项目",
  team_collaboration: "团队与协作",
  common_processes: "常用流程",
};

function ActionRow({ action, busy, onToggle, onUpdate, onDelete }: {
  action: ActionItem;
  busy: boolean;
  onToggle: (action: ActionItem) => void;
  onUpdate: (action: ActionItem, patch: Pick<ActionItem, "title" | "due_date">) => void;
  onDelete: (action: ActionItem) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(action.title);
  const [dueDate, setDueDate] = useState(action.due_date);

  function cancel() {
    setTitle(action.title);
    setDueDate(action.due_date);
    setEditing(false);
  }

  function save() {
    const nextTitle = title.trim();
    if (!nextTitle || busy) return;
    setEditing(false);
    onUpdate(action, { title: nextTitle, due_date: dueDate });
  }

  return (
    <article className={`action-row ${action.status === "done" ? "is-done" : ""} ${editing ? "is-editing" : ""}`}>
      <button type="button" className="action-check" disabled={busy} onClick={() => onToggle(action)} aria-label={action.status === "done" ? `恢复行动：${action.title}` : `完成行动：${action.title}`}>
        {action.status === "done" ? <Check size={12} /> : <Circle size={12} />}
      </button>
      {editing ? (
        <div className="action-editor">
          <input value={title} maxLength={256} onChange={(event) => setTitle(event.target.value)} aria-label={`行动标题：${action.title}`} />
          <label><CalendarDays size={12} /><input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} aria-label={`行动日期：${action.title}`} /></label>
          <div><button type="button" disabled={!title.trim() || busy} onClick={save}><Save size={12} />保存</button><button type="button" disabled={busy} onClick={cancel}><X size={12} />取消</button></div>
        </div>
      ) : (
        <>
          <div>
            <strong>{action.title}</strong>
            <small>{action.due_date || (action.source_type === "agent" ? "来自 Agent 建议" : "个人行动")}</small>
          </div>
          <div className="action-row-tools">
            <button type="button" className="action-edit" disabled={busy} onClick={() => setEditing(true)} aria-label={`编辑行动：${action.title}`}><Pencil size={12} /></button>
            <button type="button" className="action-delete" disabled={busy} onClick={() => onDelete(action)} aria-label={`删除行动：${action.title}`}><Trash2 size={13} /></button>
          </div>
        </>
      )}
    </article>
  );
}

export function ActionPlanPanel({ plan, loading, error, busy, onAccept, onDismiss, onToggle, onUpdate, onDelete }: ActionPlanPanelProps) {
  const [openSections, setOpenSections] = useState<Set<"today" | "suggestions">>(() => new Set(["today"]));
  const { ref: scrollRef, className: scrollClassName, onScroll } = useScrollAffordance();
  const done = plan?.progress.done ?? 0;
  const total = plan?.progress.total ?? 0;
  const percentage = total ? Math.round((done / total) * 100) : 0;

  function toggleSection(section: "today" | "suggestions") {
    setOpenSections((current) => {
      const next = new Set(current);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  }

  const todayOpen = openSections.has("today");
  const suggestionsOpen = openSections.has("suggestions");

  return (
    <aside className="panel action-plan-panel" aria-label="AI 入职推进">
      <div className="panel-heading">
        <div className="panel-title-wrap">
          <span className="section-symbol"><ListChecks size={16} /></span>
          <div>
            <p className="eyebrow">AI ONBOARDING</p>
            <h2>入职推进</h2>
          </div>
        </div>
        <span className="plan-progress-label">{percentage}%</span>
      </div>

      <div className={`action-plan-scroll scroll-area side-scroll ${scrollClassName}`} ref={scrollRef} onScroll={onScroll}>
        {loading && <p className="quiet-state"><LoaderCircle className="spin" size={15} />正在同步行动计划</p>}
        {!loading && error && <p className="quiet-state error-text">行动计划暂时无法加载，请稍后刷新</p>}
        {!loading && !error && (
          <>
            <section className={`plan-section plan-section-collapsible ${todayOpen ? "is-open" : ""}`}>
              <button className="plan-section-heading" type="button" onClick={() => toggleSection("today")} aria-expanded={todayOpen}>
                <Clock3 size={13} /><h3>今日重点</h3><span>{plan?.today_focus.length ?? 0}</span><ChevronDown className="plan-section-chevron" size={14} />
              </button>
              <div className="plan-section-disclosure">
                <div className="plan-section-content">
                  {(plan?.today_focus.length ?? 0) === 0
                    ? <p className="plan-empty">还没有确定的行动。先向 Agent 提一个与你当前岗位相关的问题。</p>
                    : plan!.today_focus.map((action) => <ActionRow key={action.id} action={action} busy={busy} onToggle={onToggle} onUpdate={onUpdate} onDelete={onDelete} />)}
                </div>
              </div>
            </section>

            <section className={`plan-section plan-section-collapsible ${suggestionsOpen ? "is-open" : ""}`}>
              <button className="plan-section-heading" type="button" onClick={() => toggleSection("suggestions")} aria-expanded={suggestionsOpen}>
                <Sparkles size={13} /><h3>Agent 建议</h3><span>{plan?.suggestions.length ?? 0}</span><ChevronDown className="plan-section-chevron" size={14} />
              </button>
              <div className="plan-section-disclosure">
                <div className="plan-section-content">
                  {(plan?.suggestions.length ?? 0) === 0
                    ? <p className="plan-empty">Agent 生成的行动只会作为候选，未经你确认不会加入计划。</p>
                    : plan!.suggestions.map((suggestion) => (
                      <article className="suggestion-card" key={suggestion.id}>
                        <div className="suggestion-meta"><span>{DUE_LABELS[suggestion.due_hint]}</span><span>{TOPIC_LABELS[suggestion.topic_key] ?? "入职行动"}</span></div>
                        <strong>{suggestion.title}</strong>
                        <p>{suggestion.reason}</p>
                        <div className="suggestion-actions">
                          <button type="button" disabled={busy} onClick={() => onAccept(suggestion)}><Check size={13} />加入计划</button>
                          <button type="button" disabled={busy} onClick={() => onDismiss(suggestion)}><X size={13} />暂不需要</button>
                        </div>
                      </article>
                    ))}
                </div>
              </div>
            </section>

            <section className="plan-section">
              <div className="plan-section-heading"><ListChecks size={13} /><h3>我的行动</h3><span>{plan?.actions.length ?? 0}</span></div>
              {(plan?.actions.length ?? 0) === 0
                ? <p className="plan-empty">你确认的行动会出现在这里。</p>
                : plan!.actions.map((action) => <ActionRow key={action.id} action={action} busy={busy} onToggle={onToggle} onUpdate={onUpdate} onDelete={onDelete} />)}
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
