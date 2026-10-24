import { expect, test } from "@playwright/test";
import { SCREENSHOT_DIR } from "./helpers";

test("mobile layout: bottom nav, filter drawer, no horizontal scroll", async ({ page }) => {
  await page.goto("/products");
  await expect(page.getByRole("navigation", { name: "Mobile" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/10-mobile-storefront.png` });

  await page.getByRole("button", { name: /^Filters/ }).click();
  const drawer = page.getByRole("dialog", { name: "Filters" });
  await expect(drawer).toBeVisible();
  const tools = drawer.getByRole("checkbox", { name: "Tools" });
  await tools.click();
  await expect(tools).toBeChecked();
  await expect(page).toHaveURL(/category=Tools/);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/11-mobile-filters.png` });
});

test("keyboard: skip link and search shortcut", async ({ page }) => {
  await page.goto("/products");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.locator("body").click({ position: { x: 5, y: 300 } });
  await page.keyboard.press("/");
  await expect(page.getByRole("searchbox", { name: "Search products" })).toBeFocused();
});
