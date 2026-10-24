import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against an ISOLATED stack started by Playwright:
 *   API  → http://127.0.0.1:8001 using database "flashcart_e2e" (reset before every run)
 *   Web  → http://127.0.0.1:5174 proxying /api to the e2e API
 * Requires the local MongoDB replica set (scripts/dev/start-mongo.ps1).
 */
const API_PORT = 8001;
const WEB_PORT = 5174;
// cmd.exe (used by Playwright's webServer on Windows) needs backslashes in a relative executable path.
const python = process.platform === "win32" ? String.raw`.venv\Scripts\python.exe` : ".venv/bin/python";

export const E2E_ENV = {
  FLASHCART_MONGODB_DB: "flashcart_e2e",
  FLASHCART_AUTH_RATE_LIMIT_PER_MINUTE: "200",
  FLASHCART_ADMIN_EMAIL: "",
  FLASHCART_ADMIN_PASSWORD: "",
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testIgnore: /responsive\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /responsive\.spec\.ts/ },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn app.asgi:app --host 127.0.0.1 --port ${API_PORT} --log-level warning`,
      cwd: "../flashcart-api",
      url: `http://127.0.0.1:${API_PORT}/readyz`,
      env: E2E_ENV,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { FLASHCART_API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
