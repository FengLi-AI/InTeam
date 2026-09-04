import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteAction, updateAction, updateOnboardingTopic } from "@/lib/api/workspace";

afterEach(() => vi.unstubAllGlobals());

function response(payload: unknown = { status: "ok", item: {} }) {
  return {
    ok: true,
    status: 200,
    headers: new Headers(),
    json: vi.fn().mockResolvedValue(payload),
  };
}

describe("APIG-compatible workspace writes", () => {
  it("uses POST for action and onboarding updates", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ item: { id: 7, status: "done" } }))
      .mockResolvedValueOnce(response({ item: { topic_key: "my_role", status: "completed" } }));
    vi.stubGlobal("fetch", fetchMock);

    await updateAction(7, { status: "done" });
    await updateOnboardingTopic("my_role", "completed");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/actions/7");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST" });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/onboarding-map/my_role");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST" });
  });

  it("uses the POST delete compatibility route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response());
    vi.stubGlobal("fetch", fetchMock);

    await deleteAction(7);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/actions/7/delete",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
