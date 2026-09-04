"use client";

import {
  BookOpenCheck,
  BriefcaseBusiness,
  Building2,
  Check,
  ChevronDown,
  Circle,
  FolderKanban,
  LoaderCircle,
  Network,
  Route,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

import { useScrollAffordance } from "@/features/workspace/use-scroll-affordance";
import type { OnboardingStatus, OnboardingTopic } from "@/lib/api/types";

type OnboardingMapPanelProps = {
  items: OnboardingTopic[];
  loading: boolean;
  error: boolean;
  busy: boolean;
  onAsk: (question: string, topicKey: string) => void;
  onStatusChange: (topicKey: string, status: OnboardingStatus) => void;
};

const ICONS = {
  today_start: Sparkles,
  company_business: Building2,
  my_role: BriefcaseBusiness,
  current_project: FolderKanban,
  team_collaboration: Network,
  common_processes: Route,
} as const;

const STATUS_LABELS: Record<OnboardingStatus, string> = {
  not_started: "未开始",
  exploring: "了解中",
  completed: "已完成",
};

export function OnboardingMapPanel({
  items,
  loading,
  error,
  busy,
  onAsk,
  onStatusChange,
}: OnboardingMapPanelProps) {
  const [openTopics, setOpenTopics] = useState<Set<string>>(() => new Set(["today_start"]));
  const { ref: scrollRef, className: scrollClassName, onScroll } = useScrollAffordance();

  function toggle(topicKey: string) {
    setOpenTopics((current) => {
      const next = new Set(current);
      if (next.has(topicKey)) next.delete(topicKey);
      else next.add(topicKey);
      return next;
    });
  }

  return (
    <aside className="panel onboarding-panel" aria-label="上手地图">
      <div className="panel-heading">
        <div className="panel-title-wrap">
          <span className="section-symbol"><BookOpenCheck size={16} /></span>
          <div>
            <p className="eyebrow">ONBOARDING MAP</p>
            <h2>上手地图</h2>
          </div>
        </div>
        <span className="map-count">{items.filter((item) => item.status === "completed").length}/{items.length || 6}</span>
      </div>

      <div className={`onboarding-scroll scroll-area side-scroll ${scrollClassName}`} ref={scrollRef} onScroll={onScroll}>
        {loading && <p className="quiet-state"><LoaderCircle className="spin" size={15} />正在准备上手路径</p>}
        {!loading && error && <p className="quiet-state error-text">上手地图暂时无法加载，请稍后刷新</p>}
        {!loading && !error && items.map((topic) => {
          const open = openTopics.has(topic.topic_key);
          const Icon = ICONS[topic.topic_key as keyof typeof ICONS] ?? Circle;
          return (
            <section className={`onboarding-topic status-${topic.status} ${open ? "is-open" : ""}`} key={topic.topic_key}>
              <button className="topic-trigger" type="button" onClick={() => toggle(topic.topic_key)} aria-expanded={open}>
                <span className="topic-icon"><Icon size={15} /></span>
                <span className="topic-main">
                  <strong>{topic.title}</strong>
                  <small>{STATUS_LABELS[topic.status]}{topic.open_action_count > 0 ? ` · ${topic.open_action_count} 项行动` : ""}</small>
                </span>
                <ChevronDown className="topic-chevron" size={15} />
              </button>
              <div className="topic-disclosure">
                <div className="topic-content">
                  <p>{topic.summary}</p>
                  <div className="topic-questions">
                    {topic.suggested_questions.map((question) => (
                      <button type="button" key={question} onClick={() => onAsk(question, topic.topic_key)}>{question}</button>
                    ))}
                  </div>
                  <button
                    className="topic-status-action"
                    type="button"
                    disabled={busy}
                    onClick={() => onStatusChange(topic.topic_key, topic.status === "completed" ? "exploring" : "completed")}
                  >
                    {topic.status === "completed" ? <><Circle size={13} />继续了解</> : <><Check size={13} />标记已完成</>}
                  </button>
                </div>
              </div>
            </section>
          );
        })}
      </div>
    </aside>
  );
}
