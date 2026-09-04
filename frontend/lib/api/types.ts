export type Source = {
  title: string;
  section: string;
  url?: string;
};

export type UserInfo = {
  id: number;
  name: string;
  avatar_url?: string;
  department?: string;
  position?: string;
};

export type Contact = {
  id: number;
  name: string;
  department: string;
  position: string;
  duty: string;
  when_to_ask: string;
  avatar_emoji: string;
  labels: string[];
};

export type TodoItem = {
  id: number;
  title: string;
  note: string;
  due_date: string;
  status: string;
  priority: number;
  sort_order: number;
};

export type Dashboard = {
  onboard_day: number;
  todo_done: number;
  todo_total: number;
  suggestion: string;
};

export type DocItem = {
  doc_token: string;
  title: string;
  url: string;
};

export type Message = {
  role: "user" | "assistant";
  content: string;
  retryQuestion?: string;
  sources?: Source[];
  answerId?: string;
  guard?: string;
  feedback?: boolean | null;
  askingNote?: boolean;
  suggestedQuestions?: string[];
  actionSuggestions?: AgentSuggestion[];
  relatedContacts?: Contact[];
};

export type OnboardingStatus = "not_started" | "exploring" | "completed";

export type OnboardingTopic = {
  topic_key: string;
  title: string;
  summary: string;
  suggested_questions: string[];
  status: OnboardingStatus;
  open_action_count: number;
};

export type AgentSuggestion = {
  id: number;
  client_key: string;
  title: string;
  reason: string;
  action_type: "read" | "ask" | "prepare" | "practice" | "review" | "other";
  due_hint: "today" | "within_3_days" | "this_week" | "no_date";
  topic_key: string;
  related_contact_key?: string | null;
  decision: "pending" | "accepted" | "dismissed";
};

export type ActionItem = {
  id: number;
  title: string;
  reason: string;
  status: "open" | "done";
  due_date: string;
  topic_key: string;
  source_type: "agent" | "manual";
  source_suggestion_id?: number | null;
};

export type ActionPlan = {
  today_focus: ActionItem[];
  suggestions: AgentSuggestion[];
  actions: ActionItem[];
  blockers: string[];
  progress: { done: number; total: number };
};

export type ChatDoneEvent = {
  type: "done";
  answer: string;
  conversation_id?: string;
  answer_status?: "reliable" | "limited" | "not_found" | "blocked";
  sources?: Source[];
  guard?: string;
  answer_id?: string;
  suggested_questions?: string[];
  action_suggestions?: AgentSuggestion[];
  related_contacts?: Contact[];
};

export type ChatStreamEvent =
  | { type: "status"; phase: "connecting" | "accepted" | "retrieving" | "generating" | string }
  | { type: "chunk"; text: string }
  | { type: "replace"; text: string }
  | ChatDoneEvent
  | { type: "error"; error?: { code?: string; message?: string }; retryable?: boolean };
