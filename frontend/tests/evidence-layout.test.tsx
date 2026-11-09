import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { EvidenceViewer } from "@/features/files/evidence-viewer";
import type { EvidenceView } from "@/features/files/api";
import { AuthProvider } from "@/lib/auth";

it("shows evidence as compact file entries and provides one preview close action", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ user: { id: "u", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "owner" }] })));
  render(<QueryClientProvider client={new QueryClient()}><AuthProvider><EvidenceViewer items={[{ id: "f1", original_name: "nota.png", width: 640, height: 480, size_bytes: 1024, created_at: "2026-11-09T08:00:00Z", duplicate_ids: [], mime_type: "image/png" } as EvidenceView]} /></AuthProvider></QueryClientProvider>);
  const preview = await screen.findByRole("button", { name: "Pratinjau bukti nota.png" });
  expect(preview.closest("li")).not.toBeNull();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  fireEvent.click(preview);
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getAllByRole("button", { name: "Tutup" })).toHaveLength(1);
  expect(within(dialog).getByRole("img")).toHaveAttribute("width", "640");
  fireEvent.click(within(dialog).getByRole("button", { name: "Tutup" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
