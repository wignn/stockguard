import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/lib/auth";

const navigation = vi.hoisted(() => ({ pathname: "/cases/case-1", replace: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => navigation.pathname, useRouter: () => ({ replace: navigation.replace }) }));

async function renderShell(role = "staff") {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    user: { id: "u", username: "operator" }, csrf_token: "csrf",
    memberships: [{ business_id: "b", name: "Toko Pengujian", role, is_demo: true }],
  })));
  render(<QueryClientProvider client={new QueryClient()}><AuthProvider><AppShell><h1>Detail kasus</h1></AppShell></AuthProvider></QueryClientProvider>);
  await screen.findByRole("heading", { name: "Detail kasus" });
}

it("marks the case destination active on a detail route and exposes secondary destinations through Menu", async () => {
  await renderShell();
  const mobile = screen.getByRole("navigation", { name: "Navigasi mobile" });
  expect(within(mobile).getByRole("link", { name: "Kasus" })).toHaveAttribute("aria-current", "page");
  expect(within(mobile).getByRole("link", { name: "Catat" })).toHaveAttribute("href", "/record");
  const menu = within(mobile).getByRole("button", { name: "Menu" });
  expect(menu).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(menu);
  const dialog = screen.getByRole("dialog", { name: "Menu StokGuard" });
  expect(within(dialog).getByRole("link", { name: "Produk" })).toHaveAttribute("href", "/products");
  expect(within(dialog).getByRole("button", { name: "Keluar dari akun" }).parentElement).toBe(within(dialog).getByRole("button", { name: "Tutup" }).parentElement);
  expect(within(dialog).getByRole("link", { name: "Log audit" })).toHaveAttribute("href", "/audit");
  expect(within(dialog).queryByRole("link", { name: "Tinjauan pemilik" })).not.toBeInTheDocument();
  const products = within(dialog).getByRole("link", { name: "Produk" });
  products.addEventListener("click", (event) => event.preventDefault(), { once: true });
  fireEvent.click(products);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(menu).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(menu);
  fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("shows owner review in both desktop navigation and the mobile menu for owners", async () => {
  await renderShell("owner");
  const desktop = screen.getByRole("navigation", { name: "Navigasi utama" });
  expect(within(desktop).getByRole("link", { name: "Tinjauan pemilik" })).toHaveAttribute("href", "/review");
  fireEvent.click(screen.getByRole("button", { name: "Menu" }));
  expect(within(screen.getByRole("dialog")).getByRole("link", { name: "Tinjauan pemilik" })).toHaveAttribute("href", "/review");
});

it("keeps owner-only review out of desktop navigation for staff", async () => {
  await renderShell();
  expect(within(screen.getByRole("navigation", { name: "Navigasi utama" })).queryByRole("link", { name: "Tinjauan pemilik" })).not.toBeInTheDocument();
});
