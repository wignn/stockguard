import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("owner catalog, staff ledger, and ambiguous response recovery", async ({ page }) => {
  async function login(username: string) {
    await page.goto("/login");
    await page.getByLabel("Nama pengguna").fill(username);
    await page.getByLabel("Password").fill(process.env.STOKGUARD_E2E_PASSWORD!);
    await page.getByRole("button", { name: "Masuk", exact: true }).click();
    await expect(page.getByRole("link", { name: "Produk", exact: true })).toBeVisible();
  }
  await login("e2e-owner");
  await page.getByRole("link", { name: "Produk", exact: true }).click();
  await page.getByRole("button", { name: "Tambah produk" }).click();
  await page.getByLabel("Kode produk (SKU)").fill(`RT-${Date.now()}`);
  await page.getByLabel("Nama produk").fill("Roti uji");
  await page.getByRole("button", { name: "Simpan produk" }).click();
  await expect(page.getByRole("row", { name: /Roti uji/ })).toBeVisible();
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-staff");
  await page.getByRole("link", { name: "Catat transaksi", exact: true }).click();
  const roti = page.getByRole("option", { name: /Roti uji/ });
  await expect(roti).toBeAttached();
  await page.getByLabel("Produk", { exact: true }).selectOption(await roti.getAttribute("value") as string);
  await expect(page.getByRole("option", { name: /Saldo awal/ })).toHaveCount(0);
  await page.getByLabel("Jumlah", { exact: true }).fill("24");
  await page.getByLabel("Catatan transaksi").fill("Penerimaan pagi");
  await page.getByRole("button", { name: "Catat transaksi", exact: true }).click();
  await expect(page.getByText("Transaksi tercatat.")).toBeVisible();
  await page.getByLabel("Jenis transaksi").selectOption("sale");
  await page.getByLabel("Jumlah", { exact: true }).fill("6");
  await page.getByLabel("Catatan transaksi").fill("Penjualan sore");
  let originalKey = "";
  let originalPayload = "";
  await page.route("**/api/v1/businesses/*/movements", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    originalKey = route.request().headers()["idempotency-key"];
    originalPayload = route.request().postData()!;
    await route.fetch();
    await route.abort("failed");
  }, { times: 1 });
  await page.getByRole("button", { name: "Catat transaksi", exact: true }).click();
  await expect(page.getByRole("button", { name: "Ulangi permintaan asli" })).toBeVisible();
  await page.reload();
  await page.route("**/api/v1/businesses/*/movements", async (route) => {
    if (route.request().method() === "POST") {
      expect(route.request().headers()["idempotency-key"]).toBe(originalKey);
      expect(route.request().postData()).toBe(originalPayload);
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Ulangi permintaan asli" }).click();
  await expect(page.getByText("Transaksi tercatat.")).toBeVisible();
  await page.getByRole("link", { name: "Produk", exact: true }).click();
  await expect(page.getByRole("row", { name: /Roti uji/ })).toContainText("18 Pcs");
  await expect(page.getByRole("button", { name: /Ubah Roti uji/ })).toHaveCount(0);
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-owner");
  await page.getByRole("link", { name: "Produk", exact: true }).click();
  await page.getByRole("button", { name: /Ubah Roti uji/ }).click();
  await expect(page.getByLabel("Satuan dasar")).toBeDisabled();
  await page.getByRole("button", { name: "Tutup", exact: true }).click();
  await page.getByRole("link", { name: "Riwayat transaksi", exact: true }).click();
  await expect(page.getByRole("row", { name: /Penjualan sore/ })).toHaveCount(1);
  await page.getByRole("button", { name: /Ajukan pembalikan/ }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Transaksi asli tetap tersimpan");
  await page.keyboard.press("Escape");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 360, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
