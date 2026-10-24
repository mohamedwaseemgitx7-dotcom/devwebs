import { expect, type Page } from "@playwright/test";

export const PASSWORD = "Shopper!2026x";

export function uniqueEmail(prefix = "shopper") {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

export async function signUp(page: Page, email = uniqueEmail()) {
  await page.goto("/signup");
  await page.getByLabel("Name").fill("Asha Kumar");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: /Asha Kumar/ })).toBeVisible();
  return email;
}

export async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  // Wait for the app to leave /login (i.e. the login request completed and the session cookie is set).
  // Waiting for the button to disappear is NOT enough: it is relabelled "Signing in…" while the request is
  // in flight, and navigating away at that point aborts the login.
  await expect(page).not.toHaveURL(/\/login/);
}

export async function fillAddress(page: Page) {
  await page.getByLabel("Full name").fill("Asha Kumar");
  await page.getByLabel("Address").fill("12 MG Road");
  await page.getByLabel("City").fill("Bengaluru");
  await page.getByLabel("PIN code").fill("560001");
  await page.getByLabel("Mobile number").fill("9876543210");
}

export const SCREENSHOT_DIR = "../../docs/screenshots";
