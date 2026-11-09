import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { components } from "@/lib/contracts";
import type { Page } from "@/features/products/api";

export type Stocktake = components["schemas"]["StocktakeView"];

export function useStocktakes(offset = 0, limit = 25) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["stocktakes", business?.business_id, offset, limit],
    enabled: !!business,
    queryFn: ({ signal }) =>
      api<Page<Stocktake>>(`/businesses/${business!.business_id}/stocktakes?offset=${offset}&limit=${limit}`, { signal }),
  });
}

export function useStocktake(countId: string) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["stocktake", business?.business_id, countId],
    enabled: !!business && !!countId,
    queryFn: ({ signal }) =>
      api<Stocktake>(`/businesses/${business!.business_id}/stocktakes/${countId}`, { signal }),
  });
}
