import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type OcrSuggestion = {
  name: string;
  quantity: string;
  price_rupiah: string;
};

export type OcrJobView = {
  id: string;
  file_id: string;
  retry_of_id: string | null;
  status: "queued" | "processing" | "succeeded" | "failed";
  attempts: number;
  error_code: string | null;
  result: {
    raw_text: string;
    receipt_number?: string | null;
    receipt_date?: string | null;
    lines?: OcrSuggestion[];
  } | null;
  created_at: string;
  finished_at: string | null;
};

export type DraftLineView = {
  id: string;
  position: number;
  suggestion: OcrSuggestion | null;
  product_id: string | null;
  kind:
    | "opening"
    | "inbound"
    | "sale"
    | "damage"
    | "customer_return"
    | "supplier_return"
    | null;
  quantity: string | null;
  unit_price_rupiah: string | null;
  occurred_at: string | null;
  note: string;
  status: "pending" | "confirmed";
  version: number;
  movement_id: string | null;
};

export type DraftView = {
  id: string;
  file_id: string;
  ocr_job_id: string | null;
  receipt_number: string | null;
  receipt_date: string | null;
  original_ocr: {
    raw_text: string;
    receipt_number?: string | null;
    receipt_date?: string | null;
    lines?: OcrSuggestion[];
  } | null;
  version: number;
  created_at: string;
  status: "pending" | "partial" | "confirmed";
  duplicate_ids: string[];
  lines: DraftLineView[];
};

export function useOcrJob(jobId?: string | null) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["ocr-job", business?.business_id, jobId],
    enabled: !!business && !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 1000 : false;
    },
    queryFn: () =>
      api<OcrJobView>(`/businesses/${business!.business_id}/ocr-jobs/${jobId}`),
  });
}

export function useDrafts(offset = 0, limit = 25) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["transaction-drafts", business?.business_id, offset, limit],
    enabled: !!business,
    queryFn: () =>
      api<{ items: DraftView[]; total: number; offset: number; limit: number }>(
        `/businesses/${business!.business_id}/transaction-drafts?offset=${offset}&limit=${limit}`
      ),
  });
}

export function useDraft(draftId?: string) {
  const { business } = useAuth();
  return useQuery({
    queryKey: ["transaction-draft", business?.business_id, draftId],
    enabled: !!business && !!draftId,
    queryFn: () =>
      api<DraftView>(
        `/businesses/${business!.business_id}/transaction-drafts/${draftId}`
      ),
  });
}
