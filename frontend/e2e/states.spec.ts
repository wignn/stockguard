import { expect, test } from "@playwright/test";

const screens = [
  ["Dashboard", "dashboard"],
  ["Produk", "products"],
  ["Catat transaksi", "products"],
  ["Riwayat transaksi", "movements"],
  ["Opname", "products"],
  ["Kasus selisih", "cases"],
  ["Tinjauan pemilik", "cases"],
  ["Log audit", "audit-events"],
];

for (const [name, endpoint] of screens) {
  test(`${name} shows pending, failure, and retry recovery`, async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Nama pengguna").fill("e2e-empty-owner");
    await page.getByLabel("Password").fill(process.env.STOKGUARD_E2E_PASSWORD!);
    await page.getByRole("button", { name: "Masuk", exact: true }).click();
    await expect(page.getByRole("link", { name, exact: true })).toBeVisible();
    let release: () => void = () => {};
    const held = new Promise<void>(resolve => { release = resolve; });
    await page.route(`**/api/v1/businesses/*/${endpoint}*`, async route => {
      await held;
      await route.fulfill({
        status: 503, contentType: "application/json",
        body: JSON.stringify({ error: { code: "test_unavailable", message: "Layanan uji belum tersedia." } }),
      });
    });
    await page.getByRole("link", { name, exact: true }).click();
    await expect(page.getByText("Memuat data…").first()).toBeVisible();
    release();
    await expect(page.getByRole("main").getByRole("alert").first()).toContainText("Layanan uji belum tersedia.");
    await page.unroute(`**/api/v1/businesses/*/${endpoint}*`);
    await page.getByRole("button", { name: "Muat ulang", exact: true }).first().click();
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
    await expect(page.getByText("Memuat data…")).toHaveCount(0);
  });
}
