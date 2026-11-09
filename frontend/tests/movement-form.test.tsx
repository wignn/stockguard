import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { MovementForm } from "@/features/inventory/movement-form";

function setup(empty = false) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    if (String(input).endsWith("/auth/session")) return new Response(JSON.stringify({ user: { id: "u", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "owner" }] }));
    if (String(input).includes("/products")) return new Response(JSON.stringify({ items: empty ? [] : [{ id: "p", sku: "RT", name: "Roti", unit: "Pcs", step_quantity: "1", balance_quantity: "24", balance_version: 1, active: true }], total: empty ? 0 : 1 }));
    return new Response(JSON.stringify({ error: { code: "stale_version", message: "Saldo berubah. Muat ulang." } }), { status: 409 });
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthProvider><MovementForm /></AuthProvider></QueryClientProvider>);
}

it("uses product quantity steps and retains input on conflict", async () => {
  setup();
  const product = await screen.findByLabelText("Produk");
  await screen.findByRole("option", { name: /Roti/ });
  fireEvent.change(product, { target: { value: "p" } });
  expect(screen.getByLabelText("Jumlah")).toHaveAttribute("step", "1");
  fireEvent.change(screen.getByLabelText("Jumlah"), { target: { value: "6" } });
  fireEvent.change(screen.getByLabelText("Catatan transaksi"), { target: { value: "Penjualan sore" } });
  fireEvent.click(screen.getByRole("button", { name: "Catat transaksi" }));
  await screen.findByText("Saldo berubah. Muat ulang.");
  expect(screen.getByLabelText("Jumlah")).toHaveValue(6);
  expect(screen.getByLabelText("Catatan transaksi")).toHaveValue("Penjualan sore");
});

it("searches products beyond the first catalog page", async () => {
  setup();
  await screen.findByRole("option", { name: /Roti/ });
  fireEvent.change(screen.getByLabelText("Cari produk"), { target: { value: "Roti" } });
  await screen.findByRole("option", { name: /Roti/ });
  expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("q=Roti"), expect.anything());
});

it("shows matching search results outside the closed product dropdown and lets the user choose", async () => {
  setup();
  await screen.findByRole("option", { name: /Roti/ });
  fireEvent.change(screen.getByLabelText("Cari produk"), { target: { value: "Roti" } });
  fireEvent.click(await screen.findByRole("button", { name: "Pilih Roti (RT)" }));
  expect(screen.getByLabelText("Produk")).toHaveValue("p");
  expect(screen.getByLabelText("Jumlah")).toHaveAttribute("step", "1");
});

it("distinguishes no search matches from an empty catalog", async () => {
  setup(true);
  await screen.findByText(/Belum ada produk aktif/);
  fireEvent.change(screen.getByLabelText("Cari produk"), { target: { value: "sosis" } });
  await screen.findByText(/Tidak ada produk aktif yang cocok dengan “sosis”/);
  expect(screen.queryByText(/Tambahkan produk sebelum mencatat/)).not.toBeInTheDocument();
});

it("requires a transaction reason", async () => {
  setup();
  await screen.findByRole("option", { name: /Roti/ });
  expect(screen.getByLabelText("Catatan transaksi")).toBeRequired();
});

it("shows loading and error retry states when catalog request fails", async () => {
  let attempts = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    if (String(input).endsWith("/auth/session")) return new Response(JSON.stringify({ user: { id: "u", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "owner" }] }));
    attempts += 1;
    if (attempts === 1) return new Response(JSON.stringify({ error: { code: "failed", message: "Gagal memuat katalog." } }), { status: 500 });
    return new Response(JSON.stringify({ items: [{ id: "p", sku: "RT", name: "Roti", unit: "Pcs", step_quantity: "1", balance_quantity: "24", balance_version: 1, active: true }], total: 1 }));
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthProvider><MovementForm /></AuthProvider></QueryClientProvider>);
  expect(screen.getByText(/Memuat data/)).toBeInTheDocument();
  await screen.findByText("Gagal memuat katalog.");
  fireEvent.click(screen.getByRole("button", { name: "Muat ulang" }));
  await screen.findByRole("option", { name: /Roti/ });
});

it("shows an actionable empty catalog", async () => {
  setup(true);
  await screen.findByText(/Belum ada produk aktif/);
  expect(screen.getByRole("link", { name: "Buka produk" })).toHaveAttribute("href", "/products");
});
