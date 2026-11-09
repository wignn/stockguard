import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { components } from "@/lib/contracts";
import type { Page } from "@/features/products/api";

export type Movement = components["schemas"]["MovementView"];
export function useMovements(offset = 0) {
  const { business } = useAuth();
  return useQuery({ queryKey: ["movements", business?.business_id, offset], enabled: !!business, queryFn: ({ signal }) => api<Page<Movement>>(`/businesses/${business!.business_id}/movements?offset=${offset}`, { signal }) });
}
