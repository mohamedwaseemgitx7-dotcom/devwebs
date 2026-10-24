import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { E2E_ENV } from "../playwright.config";

/** Resets the isolated e2e database and creates a throwaway admin whose password exists only for this run. */
export default function globalSetup() {
  const password = `E2e!${randomBytes(12).toString("base64url")}`;
  process.env.E2E_ADMIN_EMAIL = "e2e-admin@example.com";
  process.env.E2E_ADMIN_PASSWORD = password;
  const python = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";
  execFileSync(python, ["-m", "tests.e2e_reset"], {
    cwd: "../flashcart-api",
    env: { ...process.env, ...E2E_ENV },
    stdio: "inherit",
  });
}
