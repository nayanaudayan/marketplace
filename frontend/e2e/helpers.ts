import { expect, type Page } from "@playwright/test";

export const PASSWORD = "Passw0rd!e2e";
export const uniqueEmail = (prefix: string) => `${prefix}.${Date.now()}.${Math.floor(Math.random() * 1e5)}@example.com`;

export async function register(page: Page, role: "customer" | "seller", name = "E2E User") {
  const email = uniqueEmail(role);
  await page.goto("/register");
  if (role === "seller") await page.getByRole("radio", { name: /want to sell/i }).click();
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  return email;
}

export async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /log in/i }).last().click();
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
}

/** A customer is logged in. Adds the boAt headphones (large stock) to the cart, saves an address, places the order. */
export async function placeOrderForCheapProduct(page: Page) {
  await page.goto("/products?q=boAt");
  await page.getByRole("link", { name: "boAt Rockerz 450" }).first().click();
  await page.getByRole("button", { name: "Add to cart" }).first().click();
  await expect(page.getByRole("link", { name: "Cart" })).toContainText("1");
  await page.goto("/checkout");
  await page.getByRole("button", { name: "Add new address" }).click();
  await page.getByLabel("Address", { exact: true }).fill("221B Baker Street");
  await page.getByLabel("City").fill("Mumbai");
  await page.getByLabel("State").fill("Maharashtra");
  await page.getByLabel("Postal code").fill("400001");
  await page.getByRole("button", { name: "Save address" }).click();
  await expect(page.getByText("221B Baker Street")).toBeVisible();
  await page.getByRole("button", { name: "Place order" }).click();
  await expect(page.getByRole("heading", { name: "Complete your payment" })).toBeVisible();
}
