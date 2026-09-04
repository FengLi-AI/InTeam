import { clearLegacyToken, getLegacyToken } from "@/app/lib/auth";

import { apiRequest, jsonRequest } from "./client";
import type {
  ActionItem,
  ActionPlan,
  Contact,
  Dashboard,
  DocItem,
  OnboardingStatus,
  OnboardingTopic,
  TodoItem,
  UserInfo,
} from "./types";

export const queryKeys = {
  me: ["me"] as const,
  contacts: ["contacts"] as const,
  todos: ["todos"] as const,
  dashboard: ["dashboard"] as const,
  docs: ["docs"] as const,
  onboardingMap: ["onboarding-map"] as const,
  actions: ["actions"] as const,
};

export async function getCurrentUser() {
  const legacyToken = getLegacyToken();
  try {
    const data = await apiRequest<{ user: UserInfo }>("/me", {
      headers: legacyToken ? { Authorization: `Bearer ${legacyToken}` } : undefined,
    });
    return data.user;
  } catch {
    return null;
  } finally {
    clearLegacyToken();
  }
}

export async function loginWithInvite(inviteCode: string, nickname: string) {
  const data = await apiRequest<{ user: UserInfo }>(
    "/auth/invite",
    jsonRequest("POST", { invite_code: inviteCode, nickname }),
  );
  return data.user;
}

export async function logout() {
  await apiRequest<unknown>("/auth/logout", { method: "POST" });
  clearLegacyToken();
}

export async function getContacts() {
  return (await apiRequest<{ items?: Contact[] }>("/contacts")).items ?? [];
}

export async function getContactIntro(id: number) {
  return (await apiRequest<{ intro?: string }>(`/contacts/${id}/intro`)).intro ?? "暂时无法生成简介";
}

export async function getContactDraft(id: number) {
  return (
    await apiRequest<{ message?: string }>(`/contacts/${id}/draft`, jsonRequest("POST", {}))
  ).message ?? "暂时无法生成";
}

export async function addContactLabel(id: number, label: string) {
  await apiRequest<unknown>(`/contacts/${id}/labels`, jsonRequest("POST", { label }));
}

export async function getTodos() {
  return (await apiRequest<{ items?: TodoItem[] }>("/todos")).items ?? [];
}

export async function createTodo(title: string, dueDate: string) {
  return (
    await apiRequest<{ item: TodoItem }>(
      "/todos",
      jsonRequest("POST", { title, due_date: dueDate }),
    )
  ).item;
}

export async function updateTodo(id: number, patch: Partial<Pick<TodoItem, "status" | "due_date" | "title" | "note">>) {
  await apiRequest<unknown>(`/todos/${id}`, jsonRequest("PATCH", patch));
}

export async function deleteTodo(id: number) {
  await apiRequest<unknown>(`/todos/${id}`, { method: "DELETE" });
}

export async function getDashboard() {
  return apiRequest<Dashboard>("/dashboard");
}

export async function getDocs() {
  return (await apiRequest<{ items?: DocItem[] }>("/docs")).items ?? [];
}

export async function getDocIntro(token: string) {
  return (await apiRequest<{ intro?: string }>(`/docs/${encodeURIComponent(token)}/intro`)).intro ?? "暂无法生成导读";
}

export async function getOnboardingMap() {
  return (await apiRequest<{ items?: OnboardingTopic[] }>("/onboarding-map")).items ?? [];
}

export async function updateOnboardingTopic(topicKey: string, status: OnboardingStatus) {
  return (
    await apiRequest<{ item: OnboardingTopic }>(
      `/onboarding-map/${encodeURIComponent(topicKey)}`,
      jsonRequest("POST", { status }),
    )
  ).item;
}

export async function getActionPlan() {
  return apiRequest<ActionPlan>("/actions");
}

export async function acceptSuggestion(suggestionId: number) {
  return (
    await apiRequest<{ item: ActionItem }>(
      "/actions",
      jsonRequest("POST", { suggestion_id: suggestionId }),
    )
  ).item;
}

export async function dismissSuggestion(suggestionId: number) {
  await apiRequest<unknown>(`/suggestions/${suggestionId}/dismiss`, jsonRequest("POST", {}));
}

export async function updateAction(id: number, patch: Partial<Pick<ActionItem, "title" | "due_date" | "status">>) {
  return (
    await apiRequest<{ item: ActionItem }>(`/actions/${id}`, jsonRequest("POST", patch))
  ).item;
}

export async function deleteAction(id: number) {
  await apiRequest<unknown>(`/actions/${id}/delete`, { method: "POST" });
}

export async function stopChat(requestId: string) {
  return apiRequest<{ status: "stopped" | "stopping" }>(
    `/chat/${encodeURIComponent(requestId)}/stop`,
    { method: "POST" },
  );
}

export async function sendFeedback(answerId: string, helpful: boolean, note = "") {
  await apiRequest<unknown>("/feedback", jsonRequest("POST", { answer_id: answerId, helpful, note }));
}

export async function escalateToMentor(answerId: string | undefined, content: string) {
  return apiRequest<{ mock?: boolean; sent?: boolean }>("/escalate", {
    ...jsonRequest("POST", {
      question: content,
      context: "web 端转人工",
      answer_id: answerId ?? "",
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Idempotency-Key": answerId || crypto.randomUUID(),
    },
  });
}
