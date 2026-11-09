import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { DraftEditor } from "@/features/receipts/draft-editor";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

it("places receipt reference media and draft lines in adjacent work columns with expandable raw OCR", async () => {
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
        items: [{ id: "p1", sku: "SS", name: "Susu", unit: "Pcs", step_quantity: "1", balance_quantity: "10", balance_version: 1, active: true }],
        total: 1,
      }));
    }
    if (url.includes("/files/f1")) {
      return new Response(JSON.stringify({
        id: "f1", original_name: "nota.png", mime_type: "image/png", width: 400, height: 600, size_bytes: 2048, created_at: "2026-11-09T08:00:00Z", duplicate_ids: [], links: [],
      }));
    }
    if (url.endsWith("/transaction-drafts/d1")) {
      return new Response(JSON.stringify({
        id: "d1", file_id: "f1", ocr_job_id: null, receipt_number: "INV-01", receipt_date: "2026-11-09",
        original_ocr: { raw_text: "TOTAL 15000", receipt_number: "INV-01", receipt_date: "2026-11-09", lines: [] },
        version: 1, status: "pending", duplicate_ids: [],
        lines: [{
          id: "l1", position: 0, suggestion: { name: "Susu", quantity: "3", price_rupiah: "5000" },
          product_id: "p1", kind: "inbound", quantity: "3", unit_price_rupiah: "5000",
          occurred_at: "2026-11-09T08:00:00Z", note: "Nota masuk", status: "pending", version: 1, movement_id: null,
        }],
      }));
    }
    return new Response(JSON.stringify({ items: [], total: 0 }));
  });

  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AuthProvider>
        <DraftEditor draftId="d1" />
      </AuthProvider>
    </QueryClientProvider>
  );

  const infoSection = await screen.findByRole("region", { name: "Metadata nota" });
  const linesSection = screen.getByRole("region", { name: "Baris transaksi draf" });

  expect(infoSection.closest(".work-layout")).not.toBeNull();
  expect(linesSection.closest(".work-layout")).toBe(infoSection.closest(".work-layout"));
  expect(infoSection.closest(".work-column")).not.toBe(linesSection.closest(".work-column"));

  const ocrSummary = screen.getByText(/Teks bacaan OCR/, { selector: "summary" });
  expect(ocrSummary.closest("details")).not.toHaveAttribute("open");
  fireEvent.click(ocrSummary);
  expect(ocrSummary.closest("details")).toHaveAttribute("open");
  expect(screen.getByText("TOTAL 15000")).toBeInTheDocument();
});
