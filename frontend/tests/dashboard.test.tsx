import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { PriorityList } from "@/features/risk/priority-list";

it("uses business-wide totals and offers draft review without inventing a total from one page", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/auth/session")) return new Response(JSON.stringify({
      user: { id: "u", username: "staff" }, csrf_token: "csrf",
      memberships: [{ business_id: "b", name: "Toko", role: "staff" }],
    }));
    if (url.includes("/dashboard")) return new Response(JSON.stringify({
      active_products: 120, unresolved_cases: 90, high_priority_products: 12,
      population: "active", products: { items: [], total: 120, offset: 0, limit: 50 },
    }));
    return new Response(JSON.stringify({ items: [], total: 0 }));
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthProvider><PriorityList /></AuthProvider></QueryClientProvider>);
  const summary = await screen.findByRole("region", { name: "Ringkasan usaha" });
  expect(within(summary).getByText("120")).toBeInTheDocument();
  expect(within(summary).getByText("90")).toBeInTheDocument();
  expect(within(summary).getByText("12")).toBeInTheDocument();
  expect(within(summary).queryByText("0")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Periksa draf nota" })).toHaveAttribute("href", "/record");
  expect(screen.queryByText(/0 kasus terbuka/)).not.toBeInTheDocument();
});
