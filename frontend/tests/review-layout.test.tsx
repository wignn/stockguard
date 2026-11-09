import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import ReviewPage from "@/app/(work)/review/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

it("presents cases queue and reversal queue in adjacent work areas for owners", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/auth/session")) {
      return new Response(JSON.stringify({
        user: { id: "u-owner", username: "owner" },
        csrf_token: "csrf",
        memberships: [{ business_id: "b", name: "Toko", role: "owner" }],
      }));
    }
    if (url.includes("/cases")) {
      return new Response(JSON.stringify({
        items: [{ id: "c1", product_id: "p1", difference_quantity: "-2", estimated_value_rupiah: "10000", status: "pending_review" }],
        total: 1,
      }));
    }
    if (url.includes("/reversal-requests")) {
      return new Response(JSON.stringify({
        items: [{
          id: "r1", user_id: "u-staff", original_movement_id: "m1", reason: "Salah jumlah",
          created_at: "2026-11-09T08:00:00Z", status: "pending_review", version: 1,
        }],
        total: 1,
      }));
    }
    if (url.includes("/products")) {
      return new Response(JSON.stringify({
        items: [{ id: "p1", sku: "SS", name: "Sosis", unit: "Pcs", active: true }],
        total: 1,
      }));
    }
    return new Response(JSON.stringify({ items: [], total: 0 }));
  });

  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AuthProvider>
        <ReviewPage />
      </AuthProvider>
    </QueryClientProvider>
  );

  const casesQueue = await screen.findByRole("region", { name: "Antrean kasus selisih" });
  const reversalQueue = screen.getByRole("region", { name: "Antrean permintaan pembalikan" });

  expect(casesQueue.closest(".work-layout")).not.toBeNull();
  expect(reversalQueue.closest(".work-layout")).toBe(casesQueue.closest(".work-layout"));
  expect(casesQueue.closest(".work-column")).not.toBe(reversalQueue.closest(".work-column"));
});
