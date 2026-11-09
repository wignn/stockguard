import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { CountForm } from "@/features/stocktakes/count-form";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

function setup(baseline = "24") {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/auth/session")) {
      return new Response(JSON.stringify({ user: { id: "u", username: "staff" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "staff" }] }));
    }
    if (url.includes("/products/p")) {
      return new Response(JSON.stringify({ id: "p", sku: "RT", name: "Roti", unit: "Pcs", step_quantity: "1", cost_rupiah: "1000", balance_quantity: baseline, balance_version: 1, version: 1, active: true }));
    }
    if (url.endsWith("/stocktakes/st-1")) {
      return new Response(JSON.stringify({ id: "st-1", business_id: "b", product_id: "p", location_id: "loc", user_id: "u", status: "active", version: 1, baseline_quantity: baseline, baseline_version: 1, counted_quantity: null, difference_quantity: null, difference_percentage: null, started_at: "2026-11-09T08:00:00Z", expires_at: "2026-11-09T08:15:00Z", finalized_at: null, case_id: null }));
    }
    if (url.endsWith("/finalize") && init?.method === "POST") {
      return new Response(JSON.stringify({ error: { code: "stale_balance", message: "Saldo berubah. Hitung ulang diperlukan." } }), { status: 409 });
    }
    return new Response(JSON.stringify({ items: [], total: 0 }));
  });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AuthProvider><CountForm countId="st-1" /></AuthProvider>
    </QueryClientProvider>
  );
}

it("requires discrepancy checklist when physical count differs and retains input on conflict", async () => {
  setup("24");
  const input = await screen.findByLabelText("Jumlah fisik terhitung");
  expect(input).toHaveAttribute("step", "1");
  fireEvent.change(input, { target: { value: "18" } });
  expect(screen.getByText("-6")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Samakan Sistem/i })).not.toBeInTheDocument();
  expect(screen.queryByText(/Simulasi/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/100%/i)).not.toBeInTheDocument();

  const submitBtn = screen.getByRole("button", { name: "Selesaikan opname" });
  expect(submitBtn).toBeDisabled();

  fireEvent.click(screen.getByLabelText("Tidak ada perpindahan barang fisik selama sesi hitung berlangsung"));
  expect(submitBtn).toBeDisabled();

  fireEvent.click(screen.getByLabelText("Sudah dihitung ulang secara fisik"));
  fireEvent.click(screen.getByLabelText("Area rak pajang sudah diperiksa", { exact: false }));
  fireEvent.click(screen.getByLabelText("Area penyimpanan/gudang sudah diperiksa", { exact: false }));
  expect(submitBtn).toBeEnabled();

  fireEvent.click(submitBtn);
  await screen.findByText("Saldo berubah. Hitung ulang diperlukan.");
  expect(screen.getByLabelText("Jumlah fisik terhitung")).toHaveValue(18);
});
