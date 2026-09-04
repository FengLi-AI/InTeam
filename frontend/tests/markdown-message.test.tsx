import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownMessage } from "@/features/chat/markdown-message";

describe("MarkdownMessage", () => {
  it("renders common Markdown as readable content", () => {
    render(<MarkdownMessage>{"### 当前阶段\n\n这是 **重点**。\n\n- 第一项\n- 第二项"}</MarkdownMessage>);

    expect(screen.getByRole("heading", { name: "当前阶段", level: 3 })).toBeVisible();
    expect(screen.getByText("重点").tagName).toBe("STRONG");
    expect(screen.getByRole("list")).toBeVisible();
  });

  it("does not execute raw HTML or expose unsafe links", () => {
    const { container } = render(<MarkdownMessage>{"<script>alert('x')</script>\n\n[危险链接](javascript:alert('x'))"}</MarkdownMessage>);

    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText("危险链接").closest("a")).toBeNull();
  });
});
