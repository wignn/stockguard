import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import StocktakesPage from "@/app/(work)/stocktakes/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

it("organizes opname start and open cases into adjacent work columns with collapsed past sessions", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/auth/session")) {
      return new Response(JSON.stringify({
        user: { id: "u", username: "staff" },
        csrf_token: "csrf",
        memberships: [{ business_id: "b", name: "Toko", role: "staff" }],
      }));
    }
    if (url.includes("/products")) {
      return new Response(JSON.stringify({
        items: [{ id: "p1", sku: "SS", name: "Sosis", unit: "Pcs", active: true }],
        total: 1,
      }));
    }
    if (url.includes("/cases")) {
      return new Response(JSON.stringify({
        items: [{
          id: "c1",
          product_id: "p1",
          difference_quantity: "-2",
          estimated_value_rupiah: "10000",
          status: "investigating",
        }],
        total: 1,
      }));
    }
    if (url.includes("/stocktakes")) {
      return new Response(JSON.stringify({
        items: [{
          id: "st1",
          started_at: "2026-11-09T08:00:00Z",
          product_id: "p1",
          baseline_quantity: "10",
          counted_quantity: "8",
          difference_quantity: "-2",
          status: "finalized",
        }],
        total: 1,
      }));
    }
    return new Response(JSON.stringify({ items: [], total: 0 }));
  });

  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AuthProvider>
        <StocktakesPage />
      </AuthProvider>
    </QueryClientProvider>
  );

  const startSection = await screen.findByRole("region", { name: "Mulai opname baru" });
  const casesSection = screen.getByRole("region", { name: "Daftar kasus investigasi" });

  expect(startSection.closest(".work-layout")).not.toBeNull();
  expect(casesSection.closest(".work-layout")).toBe(startSection.closest(".work-layout"));
  expect(startSection.closest(".work-column")).not.toBe(casesSection.closest(".work-column"));

  const pastSessions = screen.getByText("Sesi opname terakhir", { selector: "summary" });
  expect(pastSessions.closest("details")).not.toHaveAttribute("open");
  fireEvent.click(pastSessions);
  expect(pastSessions.closest("details")).toHaveAttribute("open");
});
