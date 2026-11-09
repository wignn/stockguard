import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Valid 1x1 white PNG
const VALID_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
  "base64"
);

test("empty dashboard, valid/invalid upload, private preview, OCR status & polling preservation, manual draft line confirm, and audit CSV", async ({
  page,
}) => {
  async function login(username: string) {
    await page.goto("/login");
    await page.getByLabel("Nama pengguna").fill(username);
    await page.getByLabel("Password").fill(process.env.STOKGUARD_E2E_PASSWORD!);
    await page.getByRole("button", { name: "Masuk", exact: true }).click();
    await expect(page.getByRole("link", { name: "Dashboard", exact: true })).toBeVisible();
  }

  // 1. Empty business dashboard shows real zero counts, not sample 120/8/3 numbers
  await login("e2e-empty-owner");
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dashboard prioritas stok" })).toBeVisible();
  const summary = page.getByRole("region", { name: "Ringkasan usaha" });
  await expect(summary).toContainText("0");
  await expect(summary).not.toContainText("120");
  await expect(page.getByText("Belum ada produk aktif pada usaha ini.")).toBeVisible();
  await page.getByRole("button", { name: "Keluar", exact: true }).click();

  // 2. Owner in active business creates product for receipt draft confirmation
  await login("e2e-owner");
  await page.getByRole("link", { name: "Produk", exact: true }).click();
  const sku = `NT-${Date.now()}`;
  await page.getByRole("button", { name: "Tambah produk" }).click();
  await page.getByLabel("Kode produk (SKU)").fill(sku);
  await page.getByLabel("Nama produk").fill("Susu Kotak Nota");
  await page.getByLabel("Harga pokok per satuan (Rp)").fill("6000");
  await page.getByRole("button", { name: "Simpan produk" }).click();
  await expect(page.getByRole("row", { name: /Susu Kotak Nota/ })).toBeVisible();

  // Check dashboard shows rules-v1, 30-day window, and insufficient history with icon+text
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await expect(page.getByText(/rules-v1/)).toBeVisible();
  await expect(page.getByText(/30 hari terakhir/)).toBeVisible();
  await expect(page.getByRole("row", { name: /Susu Kotak Nota/ })).toContainText(
    "Histori belum cukup"
  );

  // 3. Go to Catat transaksi: test invalid file upload, then valid PNG upload + duplicate warning + private modal preview
  await page.getByRole("link", { name: "Catat transaksi", exact: true }).click();
  const fileInput = page.getByLabel("Unggah foto nota (JPG/PNG)");
  await fileInput.setInputFiles({
    name: "bukan-gambar.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("bukan gambar"),
  });
  await page.getByRole("button", { name: "Unggah foto nota", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();

  await fileInput.setInputFiles({
    name: "nota-susu.png",
    mimeType: "image/png",
    buffer: VALID_PNG,
  });
  await page.getByRole("button", { name: "Unggah foto nota", exact: true }).click();
  await expect(page.getByText("Berkas bukti berhasil diunggah.")).toBeVisible();

  // Upload same file again to verify duplicate warning (warns, does not block)
  await fileInput.setInputFiles({
    name: "nota-susu-duplikat.png",
    mimeType: "image/png",
    buffer: VALID_PNG,
  });
  await page.getByRole("button", { name: "Unggah foto nota", exact: true }).click();
  await expect(page.getByText(/Peringatan duplikat/)).toBeVisible();

  // Open private preview modal, verify image dimensions & keyboard Escape close
  await page.getByRole("button", { name: /Pratinjau bukti/ }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("1 × 1 piksel");
  const img = dialog.locator("img");
  await expect(img).toHaveAttribute("width", "1");
  await expect(img).toHaveAttribute("height", "1");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  // 4. Queue OCR job (remains queued when worker is not running or fails if retried) and create manual draft
  await page.getByRole("button", { name: "Proses OCR nota" }).click();
  await expect(page.getByText(/Antrean OCR|OCR belum berhasil/)).toBeVisible();

  await page.getByRole("button", { name: "Buat draf manual dari berkas ini" }).click();
  await expect(page).toHaveURL(/\/receipts\//);

  // 5. On draft page: add a second line or verify human edits are preserved while OCR job polls
  await page.getByLabel("Nomor nota").fill("INV-E2E-01");
  await page.getByRole("button", { name: "Simpan info nota" }).click();
  await expect(page.getByText("Informasi nota tersimpan.")).toBeVisible();

  // Fill line 1 fields and verify polling does not overwrite human edits
  const prodOpt = page.getByRole("option", { name: /Susu Kotak Nota/ }).first();
  await expect(prodOpt).toBeAttached();
  const prodId = (await prodOpt.getAttribute("value"))!;
  await page.getByLabel("Produk baris 1").selectOption(prodId);
  await page.getByLabel("Jenis transaksi baris 1").selectOption("inbound");
  await page.getByLabel("Jumlah baris 1").fill("15");
  await page.getByLabel("Catatan baris 1").fill("Nota masuk susu=15");

  // Wait briefly across a query poll cycle and verify input is still "Nota masuk susu=15"
  await page.waitForTimeout(1200);
  await expect(page.getByLabel("Catatan baris 1")).toHaveValue("Nota masuk susu=15");

  // Check reviewed box and confirm line 1 once
  await page
    .getByLabel("Saya sudah memeriksa produk, jenis, jumlah, dan waktu baris 1")
    .check();
  await page.getByRole("button", { name: "Konfirmasi & bukukan baris 1" }).click();
  await expect(page.getByText("Baris 1 berhasil dibukukan ke stok.")).toBeVisible();
  await expect(page.getByText("Sudah dibukukan")).toBeVisible();
  await expect(page.getByRole("button", { name: "Konfirmasi & bukukan baris 1" })).toHaveCount(0);

  // 6. Verify Audit page has no edit/delete buttons and CSV export matches ledger
  await page.getByRole("link", { name: "Log audit", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Log audit" })).toBeVisible();
  await expect(page.getByRole("row", { name: /movement_booked/ }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Hapus|Ubah/i })).toHaveCount(0);

  const csvLink = page.getByRole("link", { name: "Unduh CSV audit" });
  await expect(csvLink).toBeVisible();
  const csvHref = (await csvLink.getAttribute("href"))!;
  const csvResponse = await page.request.get(csvHref);
  expect(csvResponse.status()).toBe(200);
  const csvText = await csvResponse.text();
  expect(csvText).toContain("movement_booked");
  expect(csvText).toContain("15");
  expect(csvText).toContain("Nota masuk susu=15");

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 360, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
