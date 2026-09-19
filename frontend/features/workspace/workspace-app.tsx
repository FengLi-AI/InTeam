"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import Link from "next/link";
import { type CSSProperties, useEffect, useState } from "react";

import { clearLegacyToken } from "@/app/lib/auth";
import { ActionPlanPanel } from "@/features/actions/action-plan-panel";
import { InviteLogin } from "@/features/auth/invite-login";
import { AssistantPanel, AssistantModes, type AssistantMode } from "@/features/agent/assistant-panel";
import { getAgentConfig } from "@/features/agent/api";
import { AeroShardsLayer, AuroraLayer } from "@/features/effects/motion-primitives";
import { OnboardingMapPanel } from "@/features/onboarding/onboarding-map-panel";
import type { ActionItem, AgentSuggestion, OnboardingStatus } from "@/lib/api/types";
import {
  acceptSuggestion,
  deleteAction,
  dismissSuggestion,
  getActionPlan,
  getCurrentUser,
  getOnboardingMap,
  loginWithInvite,
  logout,
  queryKeys,
  updateAction,
  updateOnboardingTopic,
} from "@/lib/api/workspace";

import { MobileNav, type MobileSection } from "./mobile-nav";
import { usePanelWidths } from "./use-panel-widths";
import { WorkspaceHeader } from "./workspace-header";

type PlanOperation =
  | { type: "accept"; suggestion: AgentSuggestion }
  | { type: "dismiss"; suggestion: AgentSuggestion }
  | { type: "toggle"; action: ActionItem }
  | { type: "edit"; action: ActionItem; patch: Pick<ActionItem, "title" | "due_date"> }
  | { type: "delete"; action: ActionItem };

export function WorkspaceApp() {
  const queryClient = useQueryClient();
  const [assistantMode, setAssistantMode] = useState<AssistantMode>("chat");
  const [loginError, setLoginError] = useState("");
  const [mobileSection, setMobileSection] = useState<MobileSection>("chat");
  const [externalQuestion, setExternalQuestion] = useState<{ id: number; text: string } | null>(null);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const { libraryWidth: mapWidth, scheduleWidth: planWidth, beginResize } = usePanelWidths();

  const meQuery = useQuery({ queryKey: queryKeys.me, queryFn: getCurrentUser, staleTime: Infinity, retry: false });
  const authenticated = Boolean(meQuery.data);
  const agentConfig = useQuery({ queryKey: ["agent-config"], queryFn: getAgentConfig, enabled: authenticated, retry: false });
  const agentEnabled = agentConfig.data?.enabled !== false;
  const visibleMode = agentEnabled ? assistantMode : "chat";
  const mapQuery = useQuery({ queryKey: queryKeys.onboardingMap, queryFn: getOnboardingMap, enabled: authenticated });
  const actionsQuery = useQuery({ queryKey: queryKeys.actions, queryFn: getActionPlan, enabled: authenticated });

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 3200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const loginMutation = useMutation({
    mutationFn: ({ inviteCode, nickname }: { inviteCode: string; nickname: string }) => loginWithInvite(inviteCode, nickname),
    onMutate: () => setLoginError(""),
    onSuccess: (user) => queryClient.setQueryData(queryKeys.me, user),
    onError: (error) => setLoginError(error instanceof Error ? error.message : "邀请码无效，请重试"),
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      clearLegacyToken();
      queryClient.clear();
      queryClient.setQueryData(queryKeys.me, null);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ topicKey, status }: { topicKey: string; status: OnboardingStatus }) => updateOnboardingTopic(topicKey, status),
    onSuccess: (_item, variables) => {
      setNotice({ kind: "success", text: variables.status === "completed" ? "主题已标记为完成" : "主题已恢复为了解中" });
      return queryClient.invalidateQueries({ queryKey: queryKeys.onboardingMap });
    },
    onError: () => setNotice({ kind: "error", text: "主题状态更新失败，请稍后重试" }),
  });

  const planMutation = useMutation({
    mutationFn: async (operation: PlanOperation) => {
      if (operation.type === "accept") return acceptSuggestion(operation.suggestion.id);
      if (operation.type === "dismiss") return dismissSuggestion(operation.suggestion.id);
      if (operation.type === "toggle") {
        return updateAction(operation.action.id, { status: operation.action.status === "done" ? "open" : "done" });
      }
      if (operation.type === "edit") return updateAction(operation.action.id, operation.patch);
      return deleteAction(operation.action.id);
    },
    onSuccess: async (_result, operation) => {
      const text = {
        accept: "已加入我的行动",
        dismiss: "已移除这条候选建议",
        toggle: operation.type === "toggle" && operation.action.status === "open" ? "行动已完成" : "行动已恢复",
        edit: "行动内容已更新",
        delete: "行动已删除",
      }[operation.type];
      setNotice({ kind: "success", text });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.actions }),
        queryClient.invalidateQueries({ queryKey: queryKeys.onboardingMap }),
      ]);
    },
    onError: () => setNotice({ kind: "error", text: "操作没有保存，请稍后重试" }),
  });

  function askFromMap(question: string, topicKey: string) {
    const topic = mapQuery.data?.find((item) => item.topic_key === topicKey);
    if (topic?.status === "not_started") statusMutation.mutate({ topicKey, status: "exploring" });
    setAssistantMode("chat");
    setExternalQuestion({ id: Date.now(), text: question });
    setMobileSection("chat");
  }

  function deleteConfirmed(action: ActionItem) {
    if (window.confirm(`删除行动“${action.title}”？此操作不会影响 Agent 的原始回答。`)) {
      planMutation.mutate({ type: "delete", action });
    }
  }

  if (meQuery.isPending) {
    return (
      <main className="app-loading">
        <span className="brand-mark"><LoaderCircle className="spin" size={19} /></span>
        <p>正在准备你的入职空间</p>
        <Link className="loading-recovery" href="/">长时间没有进入？点此重新加载</Link>
      </main>
    );
  }

  if (!meQuery.data) {
    return <InviteLogin busy={loginMutation.isPending} error={loginError} onLogin={(inviteCode, nickname) => loginMutation.mutate({ inviteCode, nickname })} />;
  }

  return (
    <main
      className="workspace-page"
      data-mobile-section={mobileSection}
      style={{ "--map-size": `${mapWidth}px`, "--plan-size": `${planWidth}px` } as CSSProperties}
    >
      <div className="workspace-effects"><AuroraLayer /><AeroShardsLayer /></div>
      <WorkspaceHeader user={meQuery.data} onLogout={() => logoutMutation.mutate()}>
        <AssistantModes mode={visibleMode} agentEnabled={agentEnabled} onChange={(mode) => { setAssistantMode(mode); setMobileSection("chat"); }} />
      </WorkspaceHeader>
      <div className="workspace-grid">
        <OnboardingMapPanel
          items={mapQuery.data ?? []}
          loading={mapQuery.isPending}
          error={mapQuery.isError}
          busy={statusMutation.isPending}
          onAsk={askFromMap}
          onStatusChange={(topicKey, status) => statusMutation.mutate({ topicKey, status })}
        />
        <button className="panel-resizer map-resizer" type="button" aria-label="调整上手地图宽度" onPointerDown={(event) => beginResize("library", event)} />

        <div className="center-panel">
          <div className="chat-mobile-view">
            <AssistantPanel
              mode={visibleMode}
              agentEnabled={agentEnabled}
              externalQuestion={externalQuestion}
              onAnswerComplete={() => {
                void queryClient.invalidateQueries({ queryKey: queryKeys.actions });
                void queryClient.invalidateQueries({ queryKey: queryKeys.onboardingMap });
              }}
            />
          </div>
        </div>

        <button className="panel-resizer plan-resizer" type="button" aria-label="调整入职推进宽度" onPointerDown={(event) => beginResize("schedule", event)} />
        <ActionPlanPanel
          plan={actionsQuery.data}
          loading={actionsQuery.isPending}
          error={actionsQuery.isError}
          busy={planMutation.isPending}
          onAccept={(suggestion) => planMutation.mutate({ type: "accept", suggestion })}
          onDismiss={(suggestion) => planMutation.mutate({ type: "dismiss", suggestion })}
          onToggle={(action) => planMutation.mutate({ type: "toggle", action })}
          onUpdate={(action, patch) => planMutation.mutate({ type: "edit", action, patch })}
          onDelete={deleteConfirmed}
        />
      </div>
      <MobileNav active={mobileSection} onChange={setMobileSection} />
      {notice && <div className={`workspace-notice is-${notice.kind}`} role="status">{notice.text}</div>}
    </main>
  );
}
