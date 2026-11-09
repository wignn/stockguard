import { useQuery } from "@tanstack/react-query";
import { api, API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type AuditEventView = {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  occurred_at: string;
  changes: Record<string, unknown>;
};

export function auditCsvExportUrl(
  businessId: string,
  fromIso?: string,
  toIso?: string
): string {
  const params = new URLSearchParams();
  if (fromIso) params.set("from", fromIso);
  if (toIso) params.set("to", toIso);
  const query = params.toString();
  return `${API_BASE}/businesses/${businessId}/exports/audit.csv${query ? `?${query}` : ""}`;
}

export function useAuditEvents(
  offset = 0,
  limit = 25,
  fromIso = "",
  toIso = ""
) {
  const { business } = useAuth();
  return useQuery({
    queryKey: [
      "audit-events",
      business?.business_id,
      offset,
      limit,
      fromIso,
      toIso,
    ],
    enabled: !!business,
    queryFn: () => {
      const params = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
      });
      if (fromIso) params.set("from", fromIso);
      if (toIso) params.set("to", toIso);
      return api<{
        items: AuditEventView[];
        total: number;
        offset: number;
        limit: number;
      }>(
        `/businesses/${business!.business_id}/audit-events?${params.toString()}`
      );
    },
  });
}
