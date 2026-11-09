import { useQuery } from "@tanstack/react-query";
import type { Product } from "@/features/products/api";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type RiskAssessment = {
  priority: "high" | "medium" | "low" | "insufficient";
  rule_version: string;
  reasons: string[];
  window_start: string;
  window_end: string;
  history_sufficient: boolean;
  case_count: number;
  missing_evidence_corrections: number;
};

export type DashboardRow = {
  product: Product;
  risk: RiskAssessment;
};

export type DashboardView = {
  active_products: number;
  unresolved_cases: number;
  high_priority_products: number;
  population: string;
  products: {
    items: DashboardRow[];
    total: number;
    offset: number;
    limit: number;
  };
};

export function useDashboard(offset = 0, limit = 50) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["dashboard", business?.business_id, offset, limit],
    enabled: !!business,
    queryFn: () =>
      api<DashboardView>(
        `/businesses/${business!.business_id}/dashboard?offset=${offset}&limit=${limit}`
      ),
  });
}
