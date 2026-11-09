import { defineConfig, devices } from "@playwright/test";
import { randomUUID } from "node:crypto";

process.env.STOKGUARD_E2E_PASSWORD ||= `Browser-${randomUUID()}`;
process.env.API_ORIGIN = "http://127.0.0.1:8001";

export default defineConfig({
  testDir: "./e2e", fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:3000", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chrome" } }],
  webServer: [
    { command: "uv run --project ../backend python ../backend/scripts/e2e_server.py", url: "http://127.0.0.1:8001/health", reuseExistingServer: false, timeout: 120_000 },
    { command: "npm run dev", url: "http://127.0.0.1:3000/login", reuseExistingServer: false, timeout: 120_000 },
  ],
});
