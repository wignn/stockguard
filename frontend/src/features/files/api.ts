import { useQuery } from "@tanstack/react-query";
import type { components } from "@/lib/contracts";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type EvidenceView = components["schemas"]["EvidenceView"];

export function evidenceContentUrl(businessId: string, fileId: string): string {
  return `/api/v1/businesses/${businessId}/files/${fileId}/content`;
}

export async function uploadEvidence(businessId: string, file: File): Promise<EvidenceView> {
  const form = new FormData();
  form.append("file", file);
  return api<EvidenceView>(`/businesses/${businessId}/files`, {
    method: "POST",
    body: form,
  });
}

export async function attachCaseEvidence(
  businessId: string,
  caseId: string,
  fileId: string
): Promise<EvidenceView> {
  return api<EvidenceView>(`/businesses/${businessId}/cases/${caseId}/evidence`, {
    method: "POST",
    body: { file_id: fileId },
  });
}

export function useEvidenceFile(fileId?: string) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["evidence-file", business?.business_id, fileId],
    enabled: !!business && !!fileId,
    queryFn: () => api<EvidenceView>(`/businesses/${business!.business_id}/files/${fileId}`),
  });
}
