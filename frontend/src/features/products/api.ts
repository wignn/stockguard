import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { components } from "@/lib/contracts";

export type Product = components["schemas"]["ProductView"];
export type Page<T> = { items: T[]; total: number; offset: number; limit: number };
export function useProducts(q = "", offset = 0, limit = 25) {
  const { business } = useAuth();
  return useQuery({ queryKey: ["products", business?.business_id, q, offset, limit], enabled: !!business, queryFn: ({ signal }) => api<Page<Product>>(`/businesses/${business!.business_id}/products?q=${encodeURIComponent(q)}&offset=${offset}&limit=${limit}`, { signal }) });
}
