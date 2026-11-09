import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { SubmissionForm } from "@/features/cases/submission-form";
import { ReversalReview } from "@/features/cases/reversal-review";
import type { CaseView } from "@/features/cases/api";
import type { Product } from "@/features/products/api";
import { pendingMutations } from "@/lib/idempotency";

const session = { user: { id: "owner", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "owner" }] };
function mount(children: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthProvider>{children}</AuthProvider></QueryClientProvider>);
}

it("includes attached case evidence in the immutable submission without a missing-evidence reason", async () => {
  let submitted: Record<string, unknown> | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input).endsWith("/auth/session")) return new Response(JSON.stringify(session));
    submitted = JSON.parse(String(init?.body));
    return new Response(JSON.stringify({ id: "s1" }));
  });
  mount(<SubmissionForm caseItem={{ id: "c1", version: 1, latest_stocktake_id: "st1", difference_quantity: "-2", evidence: [{ id: "f1" }] } as CaseView} product={{ unit: "Pcs", step_quantity: "1" } as Product} onDone={() => {}} />);
  await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
  expect(screen.queryByLabelText("Alasan tanpa lampiran bukti")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Jumlah usulan"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Catatan pengajuan"), { target: { value: "Bukti nota terlampir" } });
  fireEvent.click(screen.getByRole("button", { name: "Kirim pengajuan ke pemilik" }));
  await waitFor(() => expect(submitted?.evidence_ids).toEqual(["f1"]));
  expect(submitted?.missing_evidence_reason).toBe("");
});

it("replays the original reversal decision after lost response and refresh even if balance changed", async () => {
  const posts: { body: unknown; key: string | null }[] = [];
  let balanceVersion = 1;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/auth/session")) return new Response(JSON.stringify(session));
    if (url.includes("/decisions")) {
      posts.push({ body: JSON.parse(String(init?.body)), key: new Headers(init?.headers).get("Idempotency-Key") });
      if (posts.length === 1) { balanceVersion = 2; throw new TypeError("Respons terputus"); }
      return new Response(JSON.stringify({ id: "decision1" }));
    }
    if (url.includes("/movements/")) return new Response(JSON.stringify({ product_id: "p1" }));
    if (url.includes("/products/")) return new Response(JSON.stringify({ balance_version: balanceVersion }));
    return new Response(JSON.stringify({ items: [{ id: "r1", original_movement_id: "m1", user_id: "staff", status: posts.length ? "resolved" : "pending_review", version: 1, created_at: "2026-11-09T08:00:00Z", reason: "Salah catat" }], total: 1 }));
  });
  mount(<ReversalReview />);
  fireEvent.click(await screen.findByRole("button", { name: "Setujui pembalikan" }));
  await screen.findByText("Respons terputus");
  cleanup();
  mount(<ReversalReview />);
  fireEvent.click(await screen.findByRole("button", { name: "Ulangi keputusan pembalikan asli" }));
  await screen.findByText("Keputusan pembalikan tersimpan.");
  expect(posts).toHaveLength(2);
  expect(posts[1]).toEqual(posts[0]);
  expect(pendingMutations()).toEqual([]);
});

it("clears a definitive reversal conflict so a revised decision can be sent", async () => {
  let attempts = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/auth/session")) return new Response(JSON.stringify(session));
    if (url.includes("/decisions")) {
      attempts += 1;
      return attempts === 1 ? new Response(JSON.stringify({ error: { code: "version_conflict", message: "Saldo berubah" } }), { status: 409 }) : new Response("{}");
    }
    if (url.includes("/movements/")) return new Response(JSON.stringify({ product_id: "p1" }));
    if (url.includes("/products/")) return new Response(JSON.stringify({ balance_version: attempts + 1 }));
    return new Response(JSON.stringify({ items: [{ id: "r1", original_movement_id: "m1", user_id: "staff", status: "pending_review", version: 1, created_at: "2026-11-09T08:00:00Z", reason: "Salah catat" }], total: 1 }));
  });
  mount(<ReversalReview />);
  fireEvent.click(await screen.findByRole("button", { name: "Setujui pembalikan" }));
  await screen.findByText("Saldo berubah");
  expect(pendingMutations()).toEqual([]);
  fireEvent.change(screen.getByLabelText("Catatan keputusan pembalikan"), { target: { value: "Sudah diperiksa ulang" } });
  fireEvent.click(screen.getByRole("button", { name: "Setujui pembalikan" }));
  await screen.findByText("Keputusan pembalikan tersimpan.");
  expect(attempts).toBe(2);
});
