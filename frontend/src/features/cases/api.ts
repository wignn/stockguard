import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { Product, Page } from "@/features/products/api";
import type { Movement } from "@/features/inventory/api";
import type { components } from "@/lib/contracts";

export type CaseView = components["schemas"]["CaseView"];
export type SubmissionView = components["schemas"]["SubmissionView"];
export type DecisionView = components["schemas"]["DecisionView"];

export const caseStatusNames: Record<string, string> = {
  investigating: "Sedang ditelusuri",
  pending_review: "Menunggu tinjauan pemilik",
  rejected: "Pengajuan ditolak",
  needs_recount: "Perlu hitung ulang",
  resolved: "Kasus selesai",
};
export type ReversalView = {
  id: string;
  business_id: string;
  original_movement_id: string;
  user_id: string;
  reason: string;
  status: string;
  version: number;
  created_at: string;
};

export function useProduct(productId?: string) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["product", business?.business_id, productId],
    enabled: !!business && !!productId,
    queryFn: ({ signal }) =>
      api<Product>(`/businesses/${business!.business_id}/products/${productId}`, { signal }),
  });
}

export function useCases(offset = 0, limit = 25) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["cases", business?.business_id, offset, limit],
    enabled: !!business,
    queryFn: ({ signal }) =>
      api<Page<CaseView>>(`/businesses/${business!.business_id}/cases?offset=${offset}&limit=${limit}`, { signal }),
  });
}

export function useCase(caseId: string) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["case", business?.business_id, caseId],
    enabled: !!business && !!caseId,
    queryFn: ({ signal }) =>
      api<CaseView>(`/businesses/${business!.business_id}/cases/${caseId}`, { signal }),
  });
}

export function useCaseSubmissions(caseId: string) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["case-submissions", business?.business_id, caseId],
    enabled: !!business && !!caseId,
    queryFn: ({ signal }) =>
      api<Page<SubmissionView>>(`/businesses/${business!.business_id}/cases/${caseId}/submissions?limit=50`, { signal }),
  });
}

export function useProductTimeline(productId?: string, offset = 0, limit = 25) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["timeline", business?.business_id, productId, offset, limit],
    enabled: !!business && !!productId,
    queryFn: ({ signal }) =>
      api<Page<Movement>>(`/businesses/${business!.business_id}/products/${productId}/timeline?offset=${offset}&limit=${limit}`, { signal }),
  });
}

export function useReversalRequests(offset = 0, limit = 25) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["reversals", business?.business_id, offset, limit],
    enabled: !!business,
    queryFn: ({ signal }) =>
      api<Page<ReversalView>>(`/businesses/${business!.business_id}/reversal-requests?offset=${offset}&limit=${limit}`, { signal }),
  });
}
