import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("keyboard login retains fields on invalid credentials", async ({ page }) => {
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({ status: 401, json: { error: { code: "invalid_session", message: "Masuk kembali" } } }));
  await page.route("**/api/v1/auth/login", (route) => route.fulfill({ status: 401, json: { error: { code: "invalid_credentials", message: "Nama pengguna atau password tidak sesuai." } } }));
  await page.goto("/login");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Nama pengguna")).toBeFocused();
  await page.keyboard.type("synthetic-owner");
  await page.keyboard.press("Tab");
  await page.keyboard.type("synthetic-password");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert").filter({ hasText: "tidak sesuai" })).toContainText("tidak sesuai");
  await expect(page.getByLabel("Nama pengguna")).toHaveValue("synthetic-owner");
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("synthetic-password");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 360, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
