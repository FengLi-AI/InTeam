import { describe, expect, it } from "vitest";

import { clearLegacyToken, getLegacyToken } from "@/app/lib/auth";
import { safeExternalUrl } from "@/app/lib/security";

describe("legacy session migration", () => {
  it("reads the old token only for migration and can remove it", () => {
    localStorage.setItem("inteam_token", "legacy-secret");
    expect(getLegacyToken()).toBe("legacy-secret");
    clearLegacyToken();
    expect(getLegacyToken()).toBeNull();
  });
});

describe("external source links", () => {
  it("allows approved HTTPS Feishu links", () => {
    expect(safeExternalUrl("https://tenant.feishu.cn/docx/abc")).toContain("feishu.cn");
  });

  it("blocks script URLs, plaintext URLs, and unknown hosts", () => {
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("http://open.feishu.cn/document")).toBeNull();
    expect(safeExternalUrl("https://evil.example/phish")).toBeNull();
  });
});
