import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("stocktake matching, discrepancy investigation, owner review, recount rules, and reversal review", async ({ page }) => {
  async function login(username: string) {
    await page.goto("/login");
    await page.getByLabel("Nama pengguna").fill(username);
    await page.getByLabel("Password").fill(process.env.STOKGUARD_E2E_PASSWORD!);
    await page.getByRole("button", { name: "Masuk", exact: true }).click();
    await expect(page.getByRole("link", { name: "Opname", exact: true })).toBeVisible();
  }

  // 1. Owner creates 2 products: Produk Cocok (PC) and Produk Selisih (PS)
  await login("e2e-owner");
  await page.getByRole("link", { name: "Produk", exact: true }).click();
  const suffix = Date.now();
  for (const [sku, name] of [[`PC-${suffix}`, "Kopi Cocok"], [`PS-${suffix}`, "Teh Selisih"]]) {
    await page.getByRole("button", { name: "Tambah produk" }).click();
    await page.getByLabel("Kode produk (SKU)").fill(sku);
    await page.getByLabel("Nama produk").fill(name);
    await page.getByLabel("Harga pokok per satuan (Rp)").fill("5000");
    await page.getByRole("button", { name: "Simpan produk" }).click();
    await expect(page.getByRole("row", { name: new RegExp(name) })).toBeVisible();
  }

  // Record opening 24 for both products
  await page.getByRole("link", { name: "Catat transaksi", exact: true }).click();
  for (const name of ["Kopi Cocok", "Teh Selisih"]) {
    const opt = page.getByRole("option", { name: new RegExp(name) });
    await expect(opt).toBeAttached();
    await page.getByLabel("Produk", { exact: true }).selectOption((await opt.getAttribute("value"))!);
    await page.getByLabel("Jenis transaksi").selectOption("opening");
    await page.getByLabel("Jumlah", { exact: true }).fill("24");
    await page.getByLabel("Catatan transaksi").fill(`Saldo awal ${name}`);
    await page.getByRole("button", { name: "Catat transaksi", exact: true }).click();
    await expect(page.getByText("Transaksi tercatat.")).toBeVisible();
  }

  // 2. Staff logs in: matching count on Kopi Cocok (24 -> 24) creates no case
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-staff");
  await page.getByRole("link", { name: "Opname", exact: true }).click();
  const kopiOpt = page.getByRole("option", { name: /Kopi Cocok/ });
  await expect(kopiOpt).toBeAttached();
  await page.getByLabel("Produk untuk dihitung").selectOption((await kopiOpt.getAttribute("value"))!);
  await page.getByRole("button", { name: "Mulai sesi opname" }).click();
  await expect(page).toHaveURL(/\/stocktakes\//);
  await expect(page.getByRole("button", { name: /Samakan Sistem/i })).toHaveCount(0);
  await expect(page.getByText(/Simulasi/i)).toHaveCount(0);
  await expect(page.getByText(/100%/i)).toHaveCount(0);

  await page.getByLabel("Jumlah fisik terhitung").fill("24");
  await page.getByLabel("Tidak ada perpindahan barang fisik selama sesi hitung berlangsung").check();
  await page.getByRole("button", { name: "Selesaikan opname" }).click();
  await expect(page.getByText("Jumlah fisik sesuai catatan sistem. Tidak ada kasus selisih dibuka.")).toBeVisible();

  // 3. Staff starts count on Teh Selisih (24 -> 18), verifies extend lease, checklist, and opens case
  await page.getByRole("link", { name: "Opname", exact: true }).click();
  const tehOpt = page.getByRole("option", { name: /Teh Selisih/ });
  await expect(tehOpt).toBeAttached();
  await page.getByLabel("Produk untuk dihitung").selectOption((await tehOpt.getAttribute("value"))!);
  await page.getByRole("button", { name: "Mulai sesi opname" }).click();
  await page.getByRole("button", { name: "Perpanjang 15 menit" }).click();
  await expect(page.getByText("Batas waktu sesi diperpanjang.")).toBeVisible();

  await page.getByLabel("Jumlah fisik terhitung").fill("18");
  await page.getByLabel("Tidak ada perpindahan barang fisik selama sesi hitung berlangsung").check();
  await page.getByLabel("Sudah dihitung ulang secara fisik").check();
  await page.getByLabel(/Area rak pajang sudah diperiksa/).check();
  await page.getByLabel(/Area penyimpanan\/gudang sudah diperiksa/).check();
  await page.getByRole("button", { name: "Selesaikan opname" }).click();
  await expect(page.getByRole("link", { name: "Buka kasus investigasi" })).toBeVisible();
  await page.getByRole("link", { name: "Buka kasus investigasi" }).click();
  await expect(page).toHaveURL(/\/cases\//);

  // Save findings and submit first proposal
  await page.getByLabel("Catatan temuan pemeriksaan").fill("Nota penjualan sore ditemukan belum dicatat.");
  await page.getByRole("button", { name: "Simpan temuan" }).click();
  await expect(page.getByText("Temuan pemeriksaan tersimpan.")).toBeVisible();

  await page.getByLabel("Kategori penyebab").selectOption("unrecorded_transaction");
  await page.getByLabel("Jenis tindak lanjut").selectOption("movement");
  await page.getByLabel("Jenis transaksi terlupa").selectOption("sale");
  await page.getByLabel("Jumlah usulan").fill("6");
  await page.getByLabel("Catatan pengajuan").fill("Penjualan 6 pcs belum masuk buku");
  await page.getByLabel("Alasan tanpa lampiran bukti").fill("Nota fisik masih di meja kasir");
  await page.getByRole("button", { name: "Kirim pengajuan ke pemilik" }).click();
  await expect(page.getByText("Menunggu tinjauan pemilik")).toBeVisible();

  // 4. Owner logs in: rejects first submission (note required), then requests recount, then tests self-approval block
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-owner");
  await page.getByRole("link", { name: "Tinjauan pemilik", exact: true }).click();
  await page.getByRole("link", { name: /Tinjau kasus/ }).first().click();

  await page.getByLabel("Keputusan pemilik").selectOption("reject");
  await page.getByLabel("Catatan keputusan").fill("Lengkapi detail jam transaksi.");
  await page.getByRole("button", { name: "Simpan keputusan kasus" }).click();
  await expect(page.getByText("Pengajuan ditolak")).toBeVisible();

  // Owner submits own proposal -> sees self-approval warning and 403 block if attempted
  await page.getByLabel("Kategori penyebab").selectOption("unrecorded_transaction");
  await page.getByLabel("Jenis tindak lanjut").selectOption("movement");
  await page.getByLabel("Jenis transaksi terlupa").selectOption("sale");
  await page.getByLabel("Jumlah usulan").fill("6");
  await page.getByLabel("Catatan pengajuan").fill("Pengajuan oleh pemilik sendiri");
  await page.getByLabel("Alasan tanpa lampiran bukti").fill("Pemeriksaan langsung pemilik");
  await page.getByRole("button", { name: "Kirim pengajuan ke pemilik" }).click();
  await expect(page.getByText(/Anda mengajukan usulan ini sendiri/)).toBeVisible();

  // 5. New movement happens after count -> stale submission requires recount!
  await page.getByRole("link", { name: "Catat transaksi", exact: true }).click();
  const tehMoveOpt = page.getByRole("option", { name: /Teh Selisih/ });
  await expect(tehMoveOpt).toBeAttached();
  await page.getByLabel("Produk", { exact: true }).selectOption((await tehMoveOpt.getAttribute("value"))!);
  await page.getByLabel("Jenis transaksi").selectOption("inbound");
  await page.getByLabel("Jumlah", { exact: true }).fill("2");
  await page.getByLabel("Catatan transaksi").fill("Tambahan stok mendadak");
  await page.getByRole("button", { name: "Catat transaksi", exact: true }).click();
  await expect(page.getByText("Transaksi tercatat.")).toBeVisible();

  // Staff logs in to case, sees stale warning or triggers recount required, performs recount
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-staff");
  await page.getByRole("link", { name: "Opname", exact: true }).click();
  await page.getByRole("link", { name: /Buka kasus/ }).first().click();

  // Start recount directly from case (system balance is now 26; physical is 20 -> difference -6)
  await page.getByRole("button", { name: "Mulai hitung ulang" }).click();
  await expect(page).toHaveURL(/\/stocktakes\//);
  //First count matched recount check: let's count 26 (matching!) to verify matched recount stays open in investigating/pending_review until owner approves
  await page.getByLabel("Jumlah fisik terhitung").fill("26");
  await page.getByLabel("Tidak ada perpindahan barang fisik selama sesi hitung berlangsung").check();
  await page.getByRole("button", { name: "Selesaikan opname" }).click();
  await page.getByRole("link", { name: "Buka kasus investigasi" }).click();
  await expect(page.getByText("Sedang ditelusuri")).toBeVisible();

  // Submit matched recount (no_movement / miscount)
  await page.getByLabel("Kategori penyebab").selectOption("miscount");
  await page.getByLabel("Jenis tindak lanjut").selectOption("no_movement");
  await page.getByLabel("Catatan pengajuan").fill("Salah hitung sebelumnya, stok fisik ternyata 26");
  await page.getByRole("button", { name: "Kirim pengajuan ke pemilik" }).click();
  await expect(page.getByText("Menunggu tinjauan pemilik")).toBeVisible();

  // Owner requests another recount so we also test approving missing sale 26 -> 20 (or earlier 24->18)
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-owner");
  await page.getByRole("link", { name: "Tinjauan pemilik", exact: true }).click();
  await page.getByRole("link", { name: /Tinjau kasus/ }).first().click();
  await page.getByLabel("Keputusan pemilik").selectOption("recount");
  await page.getByLabel("Catatan keputusan").fill("Hitung ulang sekali lagi bersama staf gudang.");
  await page.getByRole("button", { name: "Simpan keputusan kasus" }).click();
  await expect(page.getByText("Perlu hitung ulang")).toBeVisible();

  // Staff recounts 20 (difference -6 from 26), submits missing sale 6, and requests reversal on the +2 inbound movement!
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-staff");
  // First request reversal on the +2 inbound ("Tambahan stok mendadak")
  await page.getByRole("link", { name: "Riwayat transaksi", exact: true }).click();
  await page.getByRole("button", { name: /Ajukan pembalikan Tambahan stok mendadak/ }).click();
  await page.getByLabel("Alasan pembalikan").fill("Salah catat barang masuk 2 pcs");
  await page.getByRole("button", { name: "Kirim permintaan pembalikan" }).click();
  await expect(page.getByText("Permintaan pembalikan diajukan.")).toBeVisible();
  await page.keyboard.press("Escape");

  // Owner approves reversal first so balance returns from 26 to 24!
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-owner");
  await page.getByRole("link", { name: "Tinjauan pemilik", exact: true }).click();
  const decisionRoute = "**/api/v1/businesses/*/reversal-requests/*/decisions";
  await page.route(decisionRoute, async route => {
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    await route.abort("failed");
  }, { times: 1 });
  await page.getByRole("button", { name: "Setujui pembalikan" }).click();
  await expect(page.getByRole("button", { name: "Ulangi keputusan pembalikan asli" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Ulangi keputusan pembalikan asli" }).click();
  await expect(page.getByText("Keputusan pembalikan tersimpan.")).toBeVisible();

  // Now balance is 24! Staff recounts 18 (24 -> 18) and submits missing sale 6
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-staff");
  await page.getByRole("link", { name: "Opname", exact: true }).click();
  await page.getByRole("link", { name: /Buka kasus/ }).first().click();
  await page.getByRole("button", { name: "Mulai hitung ulang" }).click();
  await page.getByLabel("Jumlah fisik terhitung").fill("18");
  await page.getByLabel("Tidak ada perpindahan barang fisik selama sesi hitung berlangsung").check();
  await page.getByLabel("Sudah dihitung ulang secara fisik").check();
  await page.getByLabel(/Area rak pajang sudah diperiksa/).check();
  await page.getByLabel(/Area penyimpanan\/gudang sudah diperiksa/).check();
  await page.getByRole("button", { name: "Selesaikan opname" }).click();
  await page.getByRole("link", { name: "Buka kasus investigasi" }).click();

  await page.getByLabel("Kategori penyebab").selectOption("unrecorded_transaction");
  await page.getByLabel("Jenis tindak lanjut").selectOption("movement");
  await page.getByLabel("Jenis transaksi terlupa").selectOption("sale");
  await page.getByLabel("Jumlah usulan").fill("6");
  await page.getByLabel("Catatan pengajuan").fill("Penjualan 6 pcs sore hari");
  await page.getByLabel("Alasan tanpa lampiran bukti").fill("Nota kertas belum difoto");
  await page.getByRole("button", { name: "Kirim pengajuan ke pemilik" }).click();
  await expect(page.getByText("Menunggu tinjauan pemilik")).toBeVisible();

  // Owner approves case -> final balance is 18!
  await page.getByRole("button", { name: "Keluar", exact: true }).click();
  await login("e2e-owner");
  await page.getByRole("link", { name: "Tinjauan pemilik", exact: true }).click();
  await page.getByRole("link", { name: /Tinjau kasus/ }).first().click();
  await page.getByLabel("Keputusan pemilik").selectOption("approve");
  await page.getByLabel("Catatan keputusan").fill("Disetujui, sesuai nota sore.");
  await page.getByRole("button", { name: "Simpan keputusan kasus" }).click();
  await expect(page.getByText("Kasus selesai")).toBeVisible();

  await page.getByRole("link", { name: "Produk", exact: true }).click();
  await expect(page.getByRole("row", { name: /Teh Selisih/ })).toContainText("18 Pcs");

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 360, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
