"use client";
import { useId, useState, type FormEvent } from "react";
import { FormField } from "@/components/form-field";
import { uploadEvidence, type EvidenceView } from "./api";
import { EvidenceViewer } from "./evidence-viewer";
import { useAuth } from "@/lib/auth";

export function EvidenceUploader({
  label = "Unggah foto nota atau bukti (JPG/PNG)",
  actionLabel = "Unggah bukti",
  onUploaded,
  showList = true,
}: {
  label?: string;
  actionLabel?: string;
  onUploaded?: (item: EvidenceView) => void | Promise<void>;
  showList?: boolean;
}) {
  const { business } = useAuth();
  const inputId = useId();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedItems, setUploadedItems] = useState<EvidenceView[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!business) return;
    if (!selectedFile) {
      setError("Pilih berkas gambar JPG atau PNG terlebih dahulu.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const item = await uploadEvidence(business.business_id, selectedFile);
      setUploadedItems((prev) => [item, ...prev.filter((existing) => existing.id !== item.id)]);
      setNotice("Berkas bukti berhasil diunggah.");
      await onUploaded?.(item);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Berkas bukti gagal diunggah. Pastikan format JPG atau PNG maksimal 5 MiB."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="notice success">
          {notice}
        </p>
      )}
      <form onSubmit={submit} className="stack">
        <FormField
          id={inputId}
          label={label}
          hint="Format yang diterima: JPG atau PNG asli, maksimal 5 MiB dan 20 megapiksel."
        >
          <input
            id={inputId}
            type="file"
            accept="image/png,image/jpeg"
            disabled={busy}
            onChange={(event) => {
              setSelectedFile(event.target.files?.[0] || null);
              setError("");
            }}
          />
        </FormField>
        <div className="actions">
          <button type="submit" className="secondary" disabled={busy}>
            {busy ? "Mengunggah…" : actionLabel}
          </button>
        </div>
      </form>
      {showList && uploadedItems.length > 0 && (
        <EvidenceViewer items={uploadedItems} title="Berkas yang baru diunggah" />
      )}
    </div>
  );
}
