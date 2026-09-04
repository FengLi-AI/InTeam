import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnboardingMapPanel } from "@/features/onboarding/onboarding-map-panel";
import type { OnboardingTopic } from "@/lib/api/types";

const items: OnboardingTopic[] = [
  {
    topic_key: "today_start",
    title: "今日开始",
    summary: "完成第一天准备。",
    suggested_questions: ["第一天先做什么？"],
    status: "exploring",
    open_action_count: 1,
  },
  {
    topic_key: "current_project",
    title: "当前项目",
    summary: "了解当前项目。",
    suggested_questions: ["项目处于什么阶段？"],
    status: "not_started",
    open_action_count: 0,
  },
];

describe("OnboardingMapPanel", () => {
  it("allows multiple topics to stay expanded and sends the selected question", () => {
    const onAsk = vi.fn();
    render(<OnboardingMapPanel items={items} loading={false} error={false} busy={false} onAsk={onAsk} onStatusChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: /今日开始/ })).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: /当前项目/ }));
    expect(screen.getByRole("button", { name: /今日开始/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /当前项目/ })).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(screen.getByRole("button", { name: "项目处于什么阶段？" }));
    expect(onAsk).toHaveBeenCalledWith("项目处于什么阶段？", "current_project");
  });
});
