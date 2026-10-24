import { expect, test } from "@playwright/test";
import { fillAddress, SCREENSHOT_DIR, signIn, signUp } from "./helpers";

test("admin manages inventory and orders", async ({ page, browser }) => {
  // A customer places an order first (separate browser context = separate session).
  const customer = await browser.newContext();
  const shopper = await customer.newPage();
  await signUp(shopper);
  await shopper.goto("/products?in_stock=1&sort=popular");
  await shopper.locator("main article").first().getByRole("button", { name: "Add to Cart" }).click();
  await expect(shopper.getByRole("link", { name: "Cart, 1 items" })).toBeVisible();
  await shopper.goto("/checkout");
  await fillAddress(shopper);
  await shopper.getByRole("button", { name: /Place order/ }).click();
  await expect(shopper.getByRole("heading", { name: "Thank you! Your order is confirmed." })).toBeVisible();
  await customer.close();

  await signIn(page, process.env.E2E_ADMIN_EMAIL!, process.env.E2E_ADMIN_PASSWORD!);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
  await expect(page.getByText("Orders (30 days)")).toBeVisible();
  await page.screenshot({ path: `${SCREENSHOT_DIR}/07-admin-dashboard.png` });

  // Add a product, then adjust its stock.
  await page.getByRole("link", { name: "Products & inventory" }).click();
  const form = page.getByRole("form", { name: "Add product" });
  await form.getByLabel("SKU").fill("FC-E2E-0001");
  await form.getByLabel("NAME").fill("E2E Test Lamp");
  await form.getByLabel("BRAND").fill("Lumen");
  await form.getByLabel("CATEGORY").selectOption("Furniture");
  await form.getByLabel("PRICE ₹").fill("1499");
  await form.getByLabel("STOCK").fill("4");
  await form.getByRole("button", { name: "Add" }).click();
  const row = page.getByRole("row", { name: /E2E Test Lamp/ });
  await expect(row).toBeVisible();
  await row.getByLabel("Stock change for E2E Test Lamp").fill("6");
  await row.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByRole("row", { name: /E2E Test Lamp/ }).getByText("Stock is now 10")).toBeVisible();
  await page.screenshot({ path: `${SCREENSHOT_DIR}/08-admin-inventory.png` });

  // The new product is visible in the storefront.
  await page.goto("/products?q=E2E%20Test%20Lamp");
  await expect(page.getByRole("article", { name: "E2E Test Lamp" })).toBeVisible();

  // Move the customer's order through its lifecycle.
  await page.goto("/admin/orders");
  const orderRow = page.getByRole("row").filter({ hasText: "Confirmed" }).first();
  await orderRow.getByRole("button", { name: "Shipped" }).click();
  await expect(page.getByRole("row").filter({ hasText: "Shipped" }).first()).toBeVisible();
  await page.getByRole("row").filter({ hasText: "Shipped" }).first().getByRole("button", { name: "Delivered" }).click();
  await expect(page.getByRole("row").filter({ hasText: "Delivered" }).first().getByText("Final")).toBeVisible();
  await page.screenshot({ path: `${SCREENSHOT_DIR}/09-admin-orders.png` });
});
