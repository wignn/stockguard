"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useDrafts, useOcrJob, type DraftView, type OcrJobView } from "./api";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const ocrErrorMessages: Record<string, string> = {
  ocr_unavailable:
    "Mesin OCR lokal (Tesseract) belum tersedia di perangkat ini. Anda tetap dapat membuat draf manual dari berkas bukti.",
  ocr_timeout:
    "Waktu bacaan OCR melampaui batas 60 detik. Coba ulang atau buat draf manual.",
  lease_expired:
    "Pekerjaan OCR melewati batas waktu pemrosesan. Silakan coba ulang atau isi draf manual.",
};

export function JobStatus({
  jobId: initialJobId,
  fileId,
}: {
  jobId: string;
  fileId: string;
}) {
  const { business } = useAuth();
  const router = useRouter();
  const client = useQueryClient();
  const [activeJobId, setActiveJobId] = useState(initialJobId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const job = useOcrJob(activeJobId);
  const drafts = useDrafts(0, 50);

  const matchingDraft = drafts.data?.items.find(
    (item) => item.ocr_job_id === activeJobId
  );

  async function retryJob() {
    if (!business) return;
    setBusy(true);
    setError("");
    try {
      const retried = await api<OcrJobView>(
        `/businesses/${business.business_id}/ocr-jobs/${activeJobId}/retry`,
        { method: "POST" }
      );
      setActiveJobId(retried.id);
      await client.invalidateQueries({ queryKey: ["ocr-job"] });
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Gagal mencoba ulang OCR."
      );
    } finally {
      setBusy(false);
    }
  }

  async function createManualDraft() {
    if (!business) return;
    setBusy(true);
    setError("");
    try {
      const created = await api<DraftView>(
        `/businesses/${business.business_id}/transaction-drafts`,
        {
          method: "POST",
          body: { file_id: fileId, lines: [{ quantity: "1", note: "" }] },
        }
      );
      await client.invalidateQueries({ queryKey: ["transaction-drafts"] });
      router.push(`/receipts/${created.id}`);
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Draf manual belum dapat dibuat."
      );
    } finally {
      setBusy(false);
    }
  }

  if (!job.data) {
    return <p role="status">Memuat status antrean OCR…</p>;
  }

  return (
    <div className="notice stack" role="status">
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      {job.data.status === "queued" && (
        <div>
          <strong>[~] Antrean OCR: Menunggu giliran worker lokal</strong>
          <p className="muted">
            Berkas sudah masuk antrean persisten SQLite. Jika worker OCR lokal belum
            dijalankan, Anda dapat langsung membuat draf manual tanpa menunggu.
          </p>
        </div>
      )}
      {job.data.status === "processing" && (
        <div>
          <strong>[~] Sedang memproses bacaan OCR lokal…</strong>
          <p className="muted">Percobaan ke-{job.data.attempts} sedang berjalan.</p>
        </div>
      )}
      {job.data.status === "succeeded" && (
        <div>
          <strong>[✓] Bacaan OCR selesai</strong>
          <p className="muted">
            Hasil bacaan wajib diperiksa manusia sebelum dibukukan ke stok.
          </p>
          {matchingDraft && (
            <Link className="button" href={`/receipts/${matchingDraft.id}`}>
              Buka draf hasil OCR
            </Link>
          )}
        </div>
      )}
      {job.data.status === "failed" && (
        <div className="stack">
          <div>
            <strong>[!] OCR belum berhasil</strong>
            <p>
              {ocrErrorMessages[job.data.error_code || ""] ||
                `Kode kendala: ${job.data.error_code || "ocr_failed"}.`}
            </p>
          </div>
          <div className="actions">
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => void retryJob()}
            >
              Coba ulang OCR
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void createManualDraft()}
            >
              Lanjutkan dengan draf manual
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
