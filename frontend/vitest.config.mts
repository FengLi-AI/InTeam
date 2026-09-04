import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    exclude: ["**/node_modules/**", "**/._*", "e2e/**"],
  },
  resolve: {
    alias: { "@": import.meta.dirname },
  },
});
