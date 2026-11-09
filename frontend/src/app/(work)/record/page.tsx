"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { EvidenceView } from "@/features/files/api";
import { EvidenceUploader } from "@/features/files/uploader";
import { MovementForm } from "@/features/inventory/movement-form";
import { useDrafts, type DraftView, type OcrJobView } from "@/features/receipts/api";
import { JobStatus } from "@/features/receipts/job-status";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatTime } from "@/lib/format";

export default function RecordPage() {
  const { business } = useAuth();
  const router = useRouter();
  const client = useQueryClient();
  const drafts = useDrafts(0, 15);
  const [latestFile, setLatestFile] = useState<EvidenceView | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function enqueueOcr(fileId: string) {
    if (!business) return;
    setBusy(true);
    setError("");
    try {
      const job = await api<OcrJobView>(
        `/businesses/${business.business_id}/ocr-jobs`,
        {
          method: "POST",
          body: { file_id: fileId },
        }
      );
      setActiveJobId(job.id);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Antrean OCR belum dapat dibuat."
      );
    } finally {
      setBusy(false);
    }
  }

  async function createManualDraft(fileId: string) {
    if (!business) return;
    setBusy(true);
    setError("");
    try {
      const draft = await api<DraftView>(
        `/businesses/${business.business_id}/transaction-drafts`,
        {
          method: "POST",
          body: {
            file_id: fileId,
            lines: [{ quantity: "1", note: "" }],
          },
        }
      );
      await client.invalidateQueries({ queryKey: ["transaction-drafts"] });
      router.push(`/receipts/${draft.id}`);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Draf manual belum dapat dibuat."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <div>
        <h1>Catat transaksi</h1>
        <p className="muted">
          Catat satu jenis barang masuk atau keluar secara langsung, atau unggah
          foto nota untuk diperiksa menjadi draf transaksi.
        </p>
      </div>

      <div className="record-layout">
      {business && <section className="panel stack" aria-label="Pencatatan langsung"><h2>Isi transaksi langsung</h2><MovementForm key={business.business_id} /></section>}

      {business && (
        <section
          className="panel form-width stack"
          aria-label="Unggah nota dan buat draf transaksi"
        >
          <div>
            <h2>Unggah nota & draf bacaan</h2>
            <p className="muted">
              Unggah foto nota (JPG/PNG) untuk diproses OCR lokal atau diisi manual
              per baris sebelum dibukukan ke stok.
            </p>
          </div>

          {error && (
            <p role="alert" className="notice error">
              {error}
            </p>
          )}

          <EvidenceUploader
            label="Unggah foto nota (JPG/PNG)"
            actionLabel="Unggah foto nota"
            onUploaded={(item) => {
              setLatestFile(item);
              setActiveJobId(null);
            }}
          />

          {latestFile && (
            <div className="stack">
              <div className="actions">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void enqueueOcr(latestFile.id)}
                >
                  Proses OCR nota
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void createManualDraft(latestFile.id)}
                >
                  Buat draf manual dari berkas ini
                </button>
              </div>
              {activeJobId && (
                <JobStatus jobId={activeJobId} fileId={latestFile.id} />
              )}
            </div>
          )}

          {(drafts.data?.items.length || 0) > 0 && (
            <div className="stack">
              <h3>Draf nota terakhir</h3>
              <div className="table-wrap responsive-table">
                <table>
                  <caption className="sr-only">Daftar draf nota</caption>
                  <thead>
                    <tr>
                      <th>Nomor nota</th>
                      <th>Status</th>
                      <th>Dibuat</th>
                      <th>Tindakan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {drafts.data?.items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.receipt_number || "Belum diisi"}</td>
                        <td data-label="Status">{item.status === "confirmed" ? "Sudah dibukukan" : "Perlu ditinjau"}</td>
                        <td data-label="Dibuat">{formatTime(item.created_at)}</td>
                        <td>
                          <Link
                            className="button secondary"
                            href={`/receipts/${item.id}`}
                          >
                            Periksa draf
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}
      </div>
    </div>
  );
}
