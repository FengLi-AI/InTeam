import { expect, test } from "@playwright/test";

test("invite entry and core workspace are reachable", async ({ page, context }, testInfo) => {
  const requestedUrls: string[] = [];
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("request", (request) => requestedUrls.push(request.url()));
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  const sessionToken = process.env.E2E_SESSION_TOKEN;
  if (sessionToken) {
    await context.addCookies([{ name: "inteam_session", value: sessionToken, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
  }
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Open Next.js Dev Tools" })).toHaveCount(0);
  if (!sessionToken) {
    await expect(page.getByRole("heading", { name: "InTeam" })).toBeVisible();
    await expect(page.getByLabel("邀请码")).toBeVisible();
    await expect(page.getByRole("button", { name: "进入 InTeam" })).toBeVisible();

    const inviteCode = process.env.E2E_INVITE_CODE;
    if (!inviteCode) return;
    await page.getByLabel("邀请码").fill(inviteCode);
    await page.getByRole("button", { name: "进入 InTeam" }).click();
    // 未登录首屏会按预期收到一次 /me 401；工作台验收只统计登录完成后的错误。
    consoleErrors.length = 0;
    pageErrors.length = 0;
  }

  if (testInfo.project.name === "mobile") {
    await expect(page.getByRole("heading", { name: /准备干点什么/ })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "移动端主导航" })).toBeVisible();
    if (process.env.E2E_SCREENSHOT_PATH) {
      await page.screenshot({ path: process.env.E2E_SCREENSHOT_PATH, fullPage: false });
    }
    await page.getByRole("button", { name: "上手地图" }).click();
    await expect(page.getByRole("heading", { name: "上手地图" })).toBeVisible();
    await page.getByRole("button", { name: "我的计划" }).click();
    await expect(page.getByRole("heading", { name: "入职推进" })).toBeVisible();
  } else {
    await expect(page.getByRole("heading", { name: /准备干点什么/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "上手地图" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "入职推进" })).toBeVisible();
    if (process.env.E2E_SCREENSHOT_PATH) {
      await page.screenshot({ path: process.env.E2E_SCREENSHOT_PATH, fullPage: false });
    }
  }

  expect(requestedUrls.some((url) => /\/api\/v1\/(contacts|docs|todos|dashboard)(?:\?|$)/.test(url))).toBe(false);

  if (process.env.E2E_VIEWPORT_SWEEP === "true" && testInfo.project.name === "desktop") {
    for (const width of [1440, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(page.getByRole("heading", { name: "上手地图" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "入职推进" })).toBeVisible();
    }
    await page.setViewportSize({ width: 768, height: 900 });
    await expect(page.getByRole("heading", { name: "上手地图" })).toBeHidden();
    await expect(page.getByRole("heading", { name: "入职推进" })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole("navigation", { name: "移动端主导航" })).toBeVisible();
  }

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
