import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ContactDetailDrawer } from "@/features/contacts/contact-detail-drawer";
import type { Contact } from "@/lib/api/types";
import { addContactLabel, getContactDraft, getContactIntro } from "@/lib/api/workspace";

vi.mock("@/lib/api/workspace", () => ({
  addContactLabel: vi.fn(),
  getContactDraft: vi.fn(),
  getContactIntro: vi.fn(),
}));

const CONTACT: Contact = {
  id: 7,
  name: "林清",
  department: "财务部",
  position: "费用会计",
  duty: "负责费用报销与票据规范。",
  when_to_ask: "报销流程、发票要求或付款进度相关问题。",
  avatar_emoji: "🧾",
  labels: ["报销问题"],
};

function renderDrawer(onClose = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ContactDetailDrawer contact={CONTACT} onClose={onClose} />
    </QueryClientProvider>,
  );
  return onClose;
}

describe("ContactDetailDrawer", () => {
  beforeEach(() => {
    vi.mocked(getContactIntro).mockResolvedValue("先说明报销类型，再准备对应票据。");
    vi.mocked(getContactDraft).mockResolvedValue("林清你好，我想确认一下报销材料。");
    vi.mocked(addContactLabel).mockResolvedValue(undefined);
  });

  it("opens contextual colleague details and loads intro only on demand", async () => {
    renderDrawer();

    expect(screen.getByRole("dialog", { name: "林清" })).toBeVisible();
    expect(screen.getByText(CONTACT.when_to_ask)).toBeVisible();
    expect(getContactIntro).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "了解 TA" }));
    await waitFor(() => expect(screen.getByText("先说明报销类型，再准备对应票据。")).toBeVisible());
    expect(getContactIntro).toHaveBeenCalledWith(CONTACT.id, expect.anything());
  });

  it("closes from the backdrop and saves a local note", async () => {
    const onClose = renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: "备注" }));
    fireEvent.change(screen.getByLabelText("同事备注"), { target: { value: "月底结账前确认" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(screen.getByText("月底结账前确认")).toBeVisible());
    expect(addContactLabel).toHaveBeenCalledWith(CONTACT.id, "月底结账前确认");

    fireEvent.click(screen.getByRole("button", { name: "点击遮罩关闭同事详情" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
