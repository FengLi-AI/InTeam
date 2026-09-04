import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActionPlanPanel } from "@/features/actions/action-plan-panel";
import type { ActionPlan } from "@/lib/api/types";

const plan: ActionPlan = {
  today_focus: [{ id: 7, title: "确认项目范围", reason: "", status: "open", due_date: "", topic_key: "current_project", source_type: "agent", source_suggestion_id: 4 }],
  suggestions: [{ id: 4, client_key: "confirm-project", title: "阅读项目概览", reason: "先了解背景", action_type: "read", due_hint: "today", topic_key: "current_project", decision: "pending" }],
  actions: [{ id: 7, title: "确认项目范围", reason: "", status: "open", due_date: "", topic_key: "current_project", source_type: "agent", source_suggestion_id: 4 }],
  blockers: [],
  progress: { done: 0, total: 1 },
};

describe("ActionPlanPanel", () => {
  it("allows today focus and agent suggestions to collapse independently", () => {
    render(<ActionPlanPanel plan={plan} loading={false} error={false} busy={false} onAccept={vi.fn()} onDismiss={vi.fn()} onToggle={vi.fn()} onUpdate={vi.fn()} onDelete={vi.fn()} />);

    const todayTrigger = screen.getByRole("button", { name: /今日重点/ });
    const suggestionsTrigger = screen.getByRole("button", { name: /Agent 建议/ });
    expect(todayTrigger).toHaveAttribute("aria-expanded", "true");
    expect(suggestionsTrigger).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(todayTrigger);
    expect(todayTrigger).toHaveAttribute("aria-expanded", "false");
    expect(suggestionsTrigger).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(suggestionsTrigger);
    expect(suggestionsTrigger).toHaveAttribute("aria-expanded", "true");
  });

  it("keeps suggestions as explicit user decisions", () => {
    const onAccept = vi.fn();
    const onDismiss = vi.fn();
    render(<ActionPlanPanel plan={plan} loading={false} error={false} busy={false} onAccept={onAccept} onDismiss={onDismiss} onToggle={vi.fn()} onUpdate={vi.fn()} onDelete={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /加入计划/ }));
    expect(onAccept).toHaveBeenCalledWith(plan.suggestions[0]);
    fireEvent.click(screen.getByRole("button", { name: /暂不需要/ }));
    expect(onDismiss).toHaveBeenCalledWith(plan.suggestions[0]);
  });

  it("forwards completion from both focus and action lists", () => {
    const onToggle = vi.fn();
    render(<ActionPlanPanel plan={plan} loading={false} error={false} busy={false} onAccept={vi.fn()} onDismiss={vi.fn()} onToggle={onToggle} onUpdate={vi.fn()} onDelete={vi.fn()} />);

    fireEvent.click(screen.getAllByRole("button", { name: "完成行动：确认项目范围" })[0]);
    expect(onToggle).toHaveBeenCalledWith(plan.actions[0]);
  });

  it("updates an action title and date without changing it automatically", () => {
    const onUpdate = vi.fn();
    render(<ActionPlanPanel plan={plan} loading={false} error={false} busy={false} onAccept={vi.fn()} onDismiss={vi.fn()} onToggle={vi.fn()} onUpdate={onUpdate} onDelete={vi.fn()} />);

    fireEvent.click(screen.getAllByRole("button", { name: "编辑行动：确认项目范围" })[0]);
    fireEvent.change(screen.getByRole("textbox", { name: "行动标题：确认项目范围" }), { target: { value: "确认试点项目范围" } });
    fireEvent.change(screen.getByLabelText("行动日期：确认项目范围"), { target: { value: "2026-09-05" } });
    fireEvent.click(screen.getByRole("button", { name: /保存/ }));

    expect(onUpdate).toHaveBeenCalledWith(plan.actions[0], {
      title: "确认试点项目范围",
      due_date: "2026-09-05",
    });
  });
});
