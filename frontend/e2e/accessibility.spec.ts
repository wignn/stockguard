import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

for (const width of [360, 390, 768, 1440]) {
  test(`real API empty workspace is accessible at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto("/login");
    await page.getByLabel("Nama pengguna").focus();
    await page.keyboard.type("e2e-empty-owner");
    await page.keyboard.press("Tab");
    await page.keyboard.type(process.env.STOKGUARD_E2E_PASSWORD!);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("link", { name: "Dashboard", exact: true })).toBeVisible();

    for (const name of ["Usaha saya", "Dashboard", "Produk", "Catat transaksi", "Riwayat transaksi", "Opname", "Kasus selisih", "Tinjauan pemilik", "Log audit"]) {
      const link = page.getByRole("link", { name, exact: true });
      const href = await link.getAttribute("href");
      await link.focus();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(new RegExp(`${href}$`));
      await expect(page.getByRole("main")).toBeVisible();
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText("Memuat data…", { exact: true })).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const scan = await new AxeBuilder({ page }).analyze();
      expect(scan.violations.filter(item => ["critical", "serious"].includes(item.impact || ""))).toEqual([]);
    }

    await page.getByRole("link", { name: "Produk", exact: true }).click();
    await page.getByRole("button", { name: "Tambah produk" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await page.getByRole("button", { name: "Keluar", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByLabel("Nama pengguna")).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("200% layout scale preserves navigation and product actions", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/login");
  await page.getByLabel("Nama pengguna").fill("e2e-empty-owner");
  await page.getByLabel("Password").fill(process.env.STOKGUARD_E2E_PASSWORD!);
  await page.getByRole("button", { name: "Masuk", exact: true }).click();
  await page.getByRole("link", { name: "Produk", exact: true }).click();
  await page.evaluate(() => { document.documentElement.style.zoom = "2"; });
  await page.getByRole("button", { name: "Tambah produk" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Simpan produk" }).focus();
  await expect(page.getByRole("button", { name: "Simpan produk" })).toBeInViewport();
  await page.keyboard.press("Escape");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
