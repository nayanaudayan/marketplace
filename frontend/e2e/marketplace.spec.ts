import { expect, test } from "@playwright/test";
import { login, placeOrderForCheapProduct, register, uniqueEmail } from "./helpers";

const ADMIN_URL = `http://localhost:${process.env.E2E_ADMIN_PORT ?? 5184}`;
const QUERY = "lightweight laptop for programming with 16GB RAM under 70000";

test("anonymous AI search respects budget and stock, and shows extracted filters", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Natural-language product search").fill(QUERY);
  await page.getByRole("button", { name: "Search" }).click();

  await expect(page).toHaveURL(/\/search\?q=/);
  await expect(page.getByText("Understood requirements:")).toBeVisible();
  await expect(page.getByText(/Max price: ₹70,000/)).toBeVisible();
  await expect(page.getByText("RAM ≥ 16 GB", { exact: true })).toBeVisible();

  // ThinkPad (₹62,990, in stock) matches; Dell Inspiron 14 (₹72,990, over budget) and Acer Aspire Lite 14 (no stock) must not.
  await expect(page.getByRole("link", { name: "Lenovo ThinkPad E14 Gen 5" }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Dell Inspiron 14" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Acer Aspire Lite 14" })).toHaveCount(0);

  const text = await page.locator("main").innerText();
  const amounts = [...text.matchAll(/₹([\d,]+(?:\.\d+)?)/g)].map((m) => Number(m[1].replace(/,/g, "")));
  expect(amounts.length).toBeGreaterThan(0);
  for (const a of amounts) expect(a).toBeLessThanOrEqual(70_000);
});

test("customer can register, buy a product and pay successfully", async ({ page }) => {
  await register(page, "customer");
  await placeOrderForCheapProduct(page);
  await page.getByRole("button", { name: "Pay now" }).click();
  await page.getByRole("button", { name: "Simulate successful payment" }).click();

  await expect(page).toHaveURL(/\/orders\/\d+/);
  await expect(page.getByText("confirmed", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("paid", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Cart" })).not.toContainText("1");
});

test("failed payment can be retried and then succeeds", async ({ page }) => {
  await register(page, "customer");
  await placeOrderForCheapProduct(page);
  await page.getByRole("button", { name: "Pay now" }).click();
  await page.getByRole("button", { name: "Simulate failed payment" }).click();

  await expect(page).toHaveURL(/\/orders\/\d+/);
  await expect(page.getByText("failed", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry payment" }).click();
  await page.getByRole("button", { name: "Simulate successful payment" }).click();
  await expect(page.getByText("paid", { exact: true })).toBeVisible();
  await expect(page.getByText("confirmed", { exact: true }).first()).toBeVisible();
});

test("seller is blocked until an admin approves, then can create a product", async ({ page, browser, request }) => {
  const storeName = `E2E Store ${Date.now()}`;
  await register(page, "seller");
  await page.getByLabel("Store name").fill(storeName);
  await page.getByRole("button", { name: "Submit for approval" }).click();
  await expect(page.getByText(/awaiting administrator approval/)).toBeVisible();
  await expect(page.getByRole("tab", { name: "Add product" })).toHaveCount(0);

  // The API itself refuses product creation for an unapproved seller.
  const token = await page.evaluate(() => localStorage.getItem("mp_access_token"));
  const blocked = await request.post("/api/v1/products", {
    headers: { Authorization: `Bearer ${token}` },
    data: { category_id: 1, name: "Nope", description: "x", variants: [{ sku: "X", variant_name: "x", selling_price: 1, quantity: 1 }] },
    baseURL: process.env.E2E_BACKEND ?? "http://localhost:8001",
  });
  expect(blocked.status()).toBe(403);

  // Admin approves through the dashboard (separate browser context).
  const adminCtx = await browser.newContext({ baseURL: ADMIN_URL });
  const adminPage = await adminCtx.newPage();
  await login(adminPage, "admin@example.com", "Admin@123");
  await expect(adminPage.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
  // the pending seller is also surfaced on the dashboard; manage it from the Sellers page via the sidebar
  await adminPage.getByRole("navigation", { name: "Admin sections" }).getByRole("link", { name: /Sellers/ }).click();
  await expect(adminPage).toHaveURL(/\/sellers$/);
  const row = adminPage.getByRole("row", { name: new RegExp(storeName) });
  await row.getByRole("button", { name: "Approve" }).click();
  await expect(row.getByText("approved", { exact: true })).toBeVisible();
  await adminCtx.close();

  // Seller now sees the full dashboard and can list a product.
  await page.reload();
  await page.getByRole("tab", { name: "Add product" }).click();
  const productName = `E2E Gadget ${Date.now()}`;
  await page.getByLabel("Product name").fill(productName);
  await page.getByLabel("Category").selectOption({ label: "Laptops" });
  await page.getByLabel("Description").fill("A test product created by the e2e suite for programming.");
  await page.getByLabel("SKU").fill(`E2E-${Date.now()}`);
  await page.getByLabel("Variant name").fill("Default");
  await page.getByLabel("Price (₹)").fill("19999");
  await page.getByLabel("Stock").fill("5");

  // Upload a real image file from disk (1x1 PNG) instead of typing a URL.
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");
  await page.locator("#pimg").setInputFiles({ name: "photo.png", mimeType: "image/png", buffer: png });
  await expect(page.getByAltText("Product image 1")).toBeVisible();
  await expect(page.getByText("Primary", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Create product" }).click();

  await expect(page.getByRole("tab", { name: "My products", selected: true })).toBeVisible();
  await expect(page.getByRole("link", { name: productName })).toBeVisible();
  // The stored image is served back by the API and actually renders.
  const stored = page.locator('img[src^="/api/v1/media/"]').first();
  await expect(stored).toBeVisible();
  await expect.poll(() => stored.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);
});

test("role guards keep customers away from seller pages and the storefront has no admin pages", async ({ page }) => {
  await register(page, "customer");
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admin dashboard" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  await page.goto("/seller");
  await expect(page).toHaveURL(/\/$/);
});

test("anonymous visitors are sent to login for protected pages", async ({ page }) => {
  await page.goto("/cart");
  await expect(page).toHaveURL(/\/login/);
  await page.goto(ADMIN_URL + "/");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
});

test("admin portal admits only administrators and offers no sign-up or shop pages", async ({ page, browser }) => {
  // a customer account is refused by the admin portal and no session is kept
  const customerCtx = await browser.newContext();
  const email = await register(await customerCtx.newPage(), "customer");
  await customerCtx.close();

  await page.goto(ADMIN_URL + "/login");
  await expect(page.getByRole("link", { name: /create an account/i })).toHaveCount(0);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("Passw0rd!e2e");
  await page.getByRole("button", { name: /log in/i }).last().click();
  await expect(page.getByText(/administrators only/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Log out" })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("mp_access_token"))).toBeNull();

  // shop pages do not exist in the admin build
  await page.goto(ADMIN_URL + "/products");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("link", { name: "AI Search" })).toHaveCount(0);
});

test("the storefront refuses administrator sign-in and points to the admin portal", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("Admin@123");
  await page.getByRole("button", { name: /log in/i }).last().click();
  await expect(page.getByText(/sign in at the admin portal/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Log out" })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("mp_access_token"))).toBeNull();
});

test("administrator can sign in on the admin portal and reach the dashboard", async ({ page }) => {
  await page.goto(ADMIN_URL + "/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("Admin@123");
  await page.getByRole("button", { name: /log in/i }).last().click();
  await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`^${ADMIN_URL}/$`));
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("admin sidebar navigates between sections and highlights the active one", async ({ page }) => {
  await page.goto(ADMIN_URL + "/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("Admin@123");
  await page.getByRole("button", { name: /log in/i }).last().click();

  const nav = page.getByRole("navigation", { name: "Admin sections" });
  await expect(nav.getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
  for (const [label, heading, path] of [
    ["Sellers", "Sellers", "/sellers"],
    ["Orders", "Orders", "/orders"],
    ["Categories", "Categories", "/categories"],
  ]) {
    await nav.getByRole("link", { name: new RegExp(label) }).click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: new RegExp(label) })).toHaveAttribute("aria-current", "page");
  }
  // deep links work after a reload and still require the session
  await page.reload();
  await expect(page.getByRole("heading", { name: "Categories", exact: true })).toBeVisible();
});

test("admin sidebar becomes a drawer on small screens", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto(ADMIN_URL + "/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("Admin@123");
  await page.getByRole("button", { name: /log in/i }).last().click();

  await expect(page.getByRole("navigation", { name: "Admin sections" })).toHaveCount(0); // drawer closed
  await page.getByRole("button", { name: "Open menu" }).click();
  const nav = page.getByRole("navigation", { name: "Admin sections" });
  await expect(nav).toBeVisible();
  await nav.getByRole("link", { name: /Orders/ }).click();
  await expect(page).toHaveURL(/\/orders$/);
  await expect(page.getByRole("navigation", { name: "Admin sections" })).toHaveCount(0); // closed after navigating
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true); // no horizontal overflow
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login/);
});
