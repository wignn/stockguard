import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { DraftEditor } from "@/features/receipts/draft-editor";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

it("refreshes saved line versions after a definitive confirmation conflict so retry can proceed", async () => {
  let version = 1;
  let confirmAttempts = 0;
  const line = () => ({ id: "l1", position: 0, suggestion: {}, product_id: "p1", kind: "inbound", quantity: "3", unit_price_rupiah: "5000", occurred_at: "2026-11-09T08:00:00Z", note: "Nota masuk", status: "pending", version, movement_id: null });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/auth/session")) return new Response(JSON.stringify({ user: { id: "u", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "owner" }] }));
    if (url.includes("/products")) return new Response(JSON.stringify({ items: [{ id: "p1", sku: "SS", name: "Susu", unit: "Pcs", step_quantity: "1", balance_quantity: "10", balance_version: 1, active: true }], total: 1 }));
    if (url.endsWith("/confirm")) {
      confirmAttempts += 1;
      return confirmAttempts === 1 ? new Response(JSON.stringify({ error: { code: "active_stocktake", message: "Sesi hitung aktif" } }), { status: 409 }) : new Response("{}");
    }
    if (init?.method === "PATCH") {
      const payload = JSON.parse(String(init.body));
      if (payload.expected_version !== version) return new Response(JSON.stringify({ error: { code: "version_conflict", message: "Versi baris tertinggal" } }), { status: 409 });
      version += 1;
      return new Response(JSON.stringify(line()));
    }
    if (url.endsWith("/transaction-drafts/d1")) return new Response(JSON.stringify({ id: "d1", file_id: "f1", ocr_job_id: null, receipt_number: "INV", receipt_date: "2026-11-09", original_ocr: {}, version: 1, status: "pending", duplicate_ids: [], lines: [line()] }));
    return new Response(JSON.stringify({ id: "f1", original_name: "nota.png", mime_type: "image/png", width: 10, height: 10, size_bytes: 100, created_at: "2026-11-09T08:00:00Z", duplicate_ids: [], links: [] }));
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthProvider><DraftEditor draftId="d1" /></AuthProvider></QueryClientProvider>);
  fireEvent.click(await screen.findByLabelText("Saya sudah memeriksa produk, jenis, jumlah, dan waktu baris 1"));
  fireEvent.click(screen.getByRole("button", { name: "Konfirmasi & bukukan baris 1" }));
  await screen.findByText("Sesi hitung aktif");
  fireEvent.click(screen.getByRole("button", { name: "Konfirmasi & bukukan baris 1" }));
  await waitFor(() => expect(confirmAttempts).toBe(2));
  await screen.findByText("Baris 1 berhasil dibukukan ke stok.");
});

it("renders OCR raw text safely as text and preserves human edits across polling refetches", async () => {
  let pollCount = 0;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/auth/session")) {
      return new Response(
        JSON.stringify({
          user: { id: "u", username: "staff" },
          csrf_token: "csrf",
          memberships: [{ business_id: "b", name: "Toko", role: "staff" }],
        })
      );
    }
    if (url.includes("/products")) {
      return new Response(
        JSON.stringify({
          items: [
            {
              id: "p1",
              sku: "SS-01",
              name: "Susu",
              unit: "Pcs",
              step_quantity: "1",
              cost_rupiah: "5000",
              balance_quantity: "10",
              balance_version: 2,
              version: 1,
              active: true,
            },
          ],
          total: 1,
          offset: 0,
          limit: 100,
        })
      );
    }
    if (url.includes("/files/f1")) {
      return new Response(
        JSON.stringify({
          id: "f1",
          original_name: "nota.png",
          mime_type: "image/png",
          sha256: "abc",
          size_bytes: 1024,
          width: 100,
          height: 200,
          created_at: "2026-11-09T08:00:00Z",
          duplicate_ids: [],
          links: [],
        })
      );
    }
    if (url.includes("/ocr-jobs/j1")) {
      pollCount += 1;
      return new Response(
        JSON.stringify({
          id: "j1",
          file_id: "f1",
          retry_of_id: null,
          status: pollCount < 2 ? "processing" : "succeeded",
          attempts: 1,
          error_code: null,
          result: { raw_text: "<img src=x onerror=alert(1)>", lines: [] },
          created_at: "2026-11-09T08:00:00Z",
          finished_at: null,
        })
      );
    }
    if (url.endsWith("/transaction-drafts/d1")) {
      return new Response(
        JSON.stringify({
          id: "d1",
          file_id: "f1",
          ocr_job_id: "j1",
          receipt_number: "INV-01",
          receipt_date: "2026-11-09",
          original_ocr: {
            raw_text: "<img src=x onerror=alert(1)>",
            receipt_number: "INV-01",
            receipt_date: "2026-11-09",
            lines: [{ name: "Susu", quantity: "3", price_rupiah: "5000" }],
          },
          version: 1,
          created_at: "2026-11-09T08:00:00Z",
          status: "pending",
          duplicate_ids: [],
          lines: [
            {
              id: "l1",
              position: 0,
              suggestion: { name: "Susu", quantity: "3", price_rupiah: "5000" },
              product_id: null,
              kind: null,
              quantity: "3",
              unit_price_rupiah: "5000",
              occurred_at: null,
              note: "Catatan awal server",
              status: "pending",
              version: 1,
              movement_id: null,
            },
          ],
        })
      );
    }
    return new Response(JSON.stringify({ items: [], total: 0 }));
  });

  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <DraftEditor draftId="d1" />
      </AuthProvider>
    </QueryClientProvider>
  );

  const noteInput = await screen.findByLabelText("Catatan baris 1");
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
  expect(screen.getByText("Belum diperiksa")).toBeInTheDocument();

  fireEvent.change(noteInput, { target: { value: "Diedit oleh manusia" } });
  expect(noteInput).toHaveValue("Diedit oleh manusia");

  // Trigger query refetch simulating OCR polling completion; human edit must remain intact
  await client.invalidateQueries();
  expect(screen.getByLabelText("Catatan baris 1")).toHaveValue("Diedit oleh manusia");
});
