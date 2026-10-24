import { expect, test } from "@playwright/test";
import { fillAddress, SCREENSHOT_DIR, signUp, uniqueEmail } from "./helpers";

test.describe("storefront browsing", () => {
  test("lists, filters, sorts and searches products", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/products$/);
    await expect(page.getByRole("heading", { name: "Products", level: 1 })).toBeVisible();
    await expect(page.getByText(/^Showing \d+ products$/)).toBeVisible(); // count varies: other tests add products
    await expect(page.locator("main article")).toHaveCount(12);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/01-storefront-desktop.png`, fullPage: false });

    // Category filter is reflected in the URL and the results.
    // click + toBeChecked (auto-retrying) instead of check(): the router commits URL changes in a React
    // transition, so the controlled checkbox updates a moment after the click.
    const electronics = page.getByRole("complementary", { name: "Product filters" }).getByRole("checkbox", { name: "Electronics" });
    await electronics.click();
    await expect(electronics).toBeChecked();
    await expect(page).toHaveURL(/category=Electronics/);
    await expect(page.getByText(/Showing \d+ products in Electronics/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove filter Category: Electronics" })).toBeVisible();

    // Sort by price ascending → prices are non-decreasing.
    // The grid keeps showing the previous results while the new page loads, so wait for the sorted API response
    // itself (registered BEFORE the change to avoid a race), then for the grid to finish re-rendering.
    const sorted = page.waitForResponse((r) => r.url().includes("/api/v1/products?") && r.url().includes("sort=price_asc"));
    await page.getByLabel("Sort by").selectOption("price_asc");
    await sorted;
    await expect(page).toHaveURL(/sort=price_asc/);
    await expect(page.locator("main ul[aria-busy='false']")).toBeVisible();
    const prices = await page.locator("main article p.text-xl").allTextContents();
    const values = prices.map((p) => Number(p.replace(/[^\d]/g, "")));
    expect(values).toEqual([...values].sort((a, b) => a - b));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/02-filtered-sorted.png` });

    // Search from the header.
    await page.getByRole("button", { name: "Clear All" }).click();
    await page.getByRole("searchbox", { name: "Search products" }).fill("headphones");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Results for “headphones”" })).toBeVisible();
    await expect(page.locator("main article").first()).toContainText(/Headphones|Headset/);

    // Empty state.
    await page.getByRole("searchbox", { name: "Search products" }).fill("zzzz-no-such-product");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "No products match your filters" })).toBeVisible();
  });

  test("product details page", async ({ page }) => {
    await page.goto("/products");
    const first = page.locator("main article h3 a").first();
    const name = await first.textContent();
    await first.click();
    await expect(page.getByRole("heading", { level: 1, name: name! })).toBeVisible();
    await expect(page.getByText(/SKU FC-/)).toBeVisible();
    await page.screenshot({ path: `${SCREENSHOT_DIR}/03-product-detail.png` });
    await page.goto("/products/this-product-does-not-exist");
    await expect(page.getByRole("heading", { name: "Product not found" })).toBeVisible();
  });
});

test.describe("customer journey", () => {
  test("guest cart → sign up → merge → checkout → confirmation → order history", async ({ page }) => {
    await page.goto("/products?sort=popular&in_stock=1");
    const cards = page.locator("main article");
    await cards.nth(0).getByRole("button", { name: "Add to Cart" }).click();
    await expect(cards.nth(0).getByRole("button", { name: "Added ✓" })).toBeVisible();
    await cards.nth(1).getByRole("button", { name: "Add to Cart" }).click();
    await expect(page.getByRole("link", { name: "Cart, 2 items" })).toBeVisible();

    await page.getByRole("link", { name: "Cart, 2 items" }).click();
    await expect(page.getByRole("heading", { name: "Shopping cart" })).toBeVisible();
    await page.getByRole("button", { name: "Increase quantity" }).first().click();
    await expect(page.getByRole("link", { name: "Cart, 3 items" })).toBeVisible();
    await page.screenshot({ path: `${SCREENSHOT_DIR}/04-cart.png` });

    // Guest must sign in to check out; the cart follows them into the new account.
    await page.getByRole("button", { name: "Sign in to check out" }).click();
    await expect(page).toHaveURL(/\/login\?next=%2Fcheckout|\/login\?next=\/checkout/);
    await signUp(page, uniqueEmail());
    await page.goto("/cart");
    await expect(page.getByRole("link", { name: "Cart, 3 items" })).toBeVisible();

    await page.getByRole("button", { name: "Proceed to checkout" }).click();
    await expect(page.getByRole("heading", { name: "Checkout" })).toBeVisible();

    // Client-side validation blocks a bad address.
    await page.getByRole("button", { name: /Place order/ }).click();
    await expect(page.getByText("PIN code must be 6 digits")).toBeVisible();

    await fillAddress(page);
    await page.getByLabel("Next Day").check();
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05-checkout.png` });
    await page.getByRole("button", { name: /Place order/ }).click();

    await expect(page.getByRole("heading", { name: "Thank you! Your order is confirmed." })).toBeVisible();
    const orderNumber = (await page.getByRole("heading", { name: /^Order FC-/ }).textContent())!.replace("Order ", "");
    await page.screenshot({ path: `${SCREENSHOT_DIR}/06-order-confirmation.png` });
    await expect(page.getByRole("link", { name: "Cart, 0 items" })).toBeVisible();

    await page.getByRole("link", { name: "All orders" }).click();
    await expect(page.getByRole("link", { name: new RegExp(orderNumber) })).toBeVisible();
  });

  test("double-clicking Place order creates exactly one order", async ({ page }) => {
    await signUp(page);
    await page.goto("/products?in_stock=1&sort=popular");
    await page.locator("main article").first().getByRole("button", { name: "Add to Cart" }).click();
    await expect(page.getByRole("link", { name: "Cart, 1 items" })).toBeVisible();
    await page.goto("/checkout");
    await fillAddress(page);
    const button = page.getByRole("button", { name: /Place order/ });
    await button.dblclick();
    await expect(page.getByRole("heading", { name: "Thank you! Your order is confirmed." })).toBeVisible();
    await page.goto("/orders");
    await expect(page.locator("main ul li")).toHaveCount(1);
  });

  test("customers cannot open admin pages and unsafe redirects are ignored", async ({ page }) => {
    await signUp(page);
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Admins only" })).toBeVisible();
    await page.getByRole("button", { name: /Asha Kumar/ }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await page.goto("/login?next=//evil.example.com");
    await expect(page).toHaveURL(/\/login/);
  });
});
