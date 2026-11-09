"use client";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FormField } from "@/components/form-field";
import { QueryState } from "@/components/query-state";
import { useEvidenceFile } from "@/features/files/api";
import { EvidenceViewer } from "@/features/files/evidence-viewer";
import { movementNames } from "@/features/inventory/movement-form";
import { useProducts, type Product } from "@/features/products/api";
import { useDraft, useOcrJob, type DraftLineView } from "./api";
import { JobStatus } from "./job-status";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  completeMutation,
  pendingMutations,
  prepareMutation,
  type PendingMutation,
} from "@/lib/idempotency";

type LineDraftState = {
  product_id: string;
  kind:
    | "opening"
    | "inbound"
    | "sale"
    | "damage"
    | "customer_return"
    | "supplier_return";
  quantity: string;
  unit_price_rupiah: string;
  note: string;
  reviewed: boolean;
};

function LineRowEditor({
  draftId,
  line,
  index,
  products,
  isOwner,
  onChanged,
}: {
  draftId: string;
  line: DraftLineView;
  index: number;
  products: Product[];
  isOwner: boolean;
  onChanged: () => void;
}) {
  const { business } = useAuth();
  const client = useQueryClient();
  const scope = `draft-confirm:${business?.business_id}:${draftId}:${line.id}`;
  const [pending, setPending] = useState<PendingMutation | undefined>(() =>
    typeof window === "undefined"
      ? undefined
      : pendingMutations().find((item) => item.scope === scope)
  );
  // Local state initialized once from `line` so background OCR polling or query refetches never overwrite human edits
  const [values, setValues] = useState<LineDraftState>(() => ({
    product_id: line.product_id || products[0]?.id || "",
    kind: line.kind || "inbound",
    quantity: line.quantity || line.suggestion?.quantity || "1",
    unit_price_rupiah: line.unit_price_rupiah || line.suggestion?.price_rupiah || "",
    note: line.note || "",
    reviewed: false,
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const activeProductId = values.product_id || products[0]?.id || "";
  const selectedProduct = products.find((p) => p.id === activeProductId);
  const rowNumber = index + 1;

  async function saveLineEdits(currentVersion: number): Promise<DraftLineView> {
    return api<DraftLineView>(
      `/businesses/${business!.business_id}/transaction-drafts/${draftId}/lines/${line.id}`,
      {
        method: "PATCH",
        body: {
          expected_version: currentVersion,
          product_id: activeProductId || null,
          kind: values.kind,
          quantity: values.quantity.trim(),
          unit_price_rupiah: values.unit_price_rupiah.trim() || null,
          occurred_at: line.occurred_at || new Date().toISOString(),
          note: values.note.trim(),
        },
      }
    );
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    if (!business) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await saveLineEdits(line.version);
      setNotice(`Perubahan baris ${rowNumber} tersimpan.`);
      await client.invalidateQueries({
        queryKey: ["transaction-draft", business.business_id, draftId],
      });
      onChanged();
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : `Baris ${rowNumber} belum tersimpan.`
      );
    } finally {
      setBusy(false);
    }
  }

  async function sendConfirm(item: PendingMutation) {
    if (!business) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(
        `/businesses/${business.business_id}/transaction-drafts/${draftId}/lines/${line.id}/confirm`,
        {
          method: "POST",
          body: item.payload,
          idempotencyKey: item.id,
        }
      );
      completeMutation(item.id);
      setPending(undefined);
      setNotice(`Baris ${rowNumber} berhasil dibukukan ke stok.`);
      await client.invalidateQueries();
      onChanged();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status < 500) {
        completeMutation(item.id);
        setPending(undefined);
        await client.invalidateQueries({
          queryKey: ["transaction-draft", business.business_id, draftId],
        });
        onChanged();
      } else {
        setPending(item);
      }
      setError(
        failure instanceof Error
          ? failure.message
          : `Konfirmasi baris ${rowNumber} gagal.`
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!business) return;
    if (!selectedProduct) {
      setError("Pilih produk terdaftar terlebih dahulu.");
      return;
    }
    if (!values.reviewed) {
      setError(
        "Centang pernyataan pemeriksaan sebelum membukukan baris ke stok."
      );
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updatedLine = await saveLineEdits(line.version);
      const item = prepareMutation(scope, {
        expected_line_version: updatedLine.version,
        expected_balance_version: selectedProduct.balance_version,
        reviewed: true,
      });
      setPending(item);
      await sendConfirm(item);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : `Baris ${rowNumber} belum dapat dikonfirmasi.`
      );
      setBusy(false);
    }
  }

  const allowedKinds = (
    ["opening", "inbound", "sale", "damage", "customer_return", "supplier_return"] as const
  ).filter((item) => isOwner || item !== "opening");

  return (
    <section
      className="panel stack"
      aria-label={`Baris draf ${rowNumber}`}
    >
      <div className="page-heading">
        <div>
          <h3>Baris {rowNumber}</h3>
          {line.suggestion && (
            <p className="muted">
              Usulan bacaan OCR (belum terverifikasi):{" "}
              <strong>{line.suggestion.name}</strong> · Jumlah:{" "}
              {line.suggestion.quantity} · Harga: Rp {line.suggestion.price_rupiah}
            </p>
          )}
        </div>
        <span className="badge">
          {line.status === "confirmed" ? "Sudah dibukukan" : "Belum diperiksa"}
        </span>
      </div>

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

      {pending && (
        <div className="notice">
          <p>Konfirmasi baris sebelumnya belum mendapat kepastian jaringan.</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => void sendConfirm(pending)}
          >
            Ulangi konfirmasi baris {rowNumber}
          </button>
        </div>
      )}

      {line.status === "confirmed" ? (
        <p className="muted">
          Baris telah tercatat di buku stok ({movementNames[line.kind || "inbound"] || line.kind},{" "}
          jumlah {line.quantity}). Baris ini bersifat permanen dan tidak dapat diubah ulang.
        </p>
      ) : (
        <form onSubmit={handleSave} className="stack">
          <fieldset disabled={busy || !!pending}>
            <div className="split">
              <FormField
                id={`line-product-${line.id}`}
                label={`Produk baris ${rowNumber}`}
              >
                <select
                  id={`line-product-${line.id}`}
                  value={activeProductId}
                  onChange={(event) =>
                    setValues((prev) => ({
                      ...prev,
                      product_id: event.target.value,
                    }))
                  }
                >
                  {products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name} ({product.sku})
                    </option>
                  ))}
                </select>
              </FormField>

              <FormField
                id={`line-kind-${line.id}`}
                label={`Jenis transaksi baris ${rowNumber}`}
              >
                <select
                  id={`line-kind-${line.id}`}
                  value={values.kind}
                  onChange={(event) =>
                    setValues((prev) => ({
                      ...prev,
                      kind: event.target.value as LineDraftState["kind"],
                    }))
                  }
                >
                  {allowedKinds.map((kind) => (
                    <option key={kind} value={kind}>
                      {movementNames[kind]}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>

            <div className="split">
              <FormField
                id={`line-qty-${line.id}`}
                label={`Jumlah baris ${rowNumber}`}
                hint={
                  selectedProduct
                    ? `Satuan ${selectedProduct.unit}, kelipatan ${selectedProduct.step_quantity}`
                    : undefined
                }
              >
                <input
                  id={`line-qty-${line.id}`}
                  type="number"
                  min={selectedProduct?.step_quantity || "0.001"}
                  step={selectedProduct?.step_quantity || "0.001"}
                  required
                  value={values.quantity}
                  onChange={(event) =>
                    setValues((prev) => ({
                      ...prev,
                      quantity: event.target.value,
                    }))
                  }
                />
              </FormField>

              <FormField
                id={`line-price-${line.id}`}
                label={`Harga satuan nota baris ${rowNumber} (Rp, opsional)`}
              >
                <input
                  id={`line-price-${line.id}`}
                  type="number"
                  min="0"
                  step="1"
                  value={values.unit_price_rupiah}
                  onChange={(event) =>
                    setValues((prev) => ({
                      ...prev,
                      unit_price_rupiah: event.target.value,
                    }))
                  }
                />
              </FormField>
            </div>

            <FormField
              id={`line-note-${line.id}`}
              label={`Catatan baris ${rowNumber}`}
            >
              <input
                id={`line-note-${line.id}`}
                required
                value={values.note}
                onChange={(event) =>
                  setValues((prev) => ({
                    ...prev,
                    note: event.target.value,
                  }))
                }
              />
            </FormField>

            <label className="check-label">
              <input
                type="checkbox"
                checked={values.reviewed}
                onChange={(event) =>
                  setValues((prev) => ({
                    ...prev,
                    reviewed: event.target.checked,
                  }))
                }
              />
              Saya sudah memeriksa produk, jenis, jumlah, dan waktu baris{" "}
              {rowNumber}
            </label>

            <div className="actions">
              <button type="submit" className="secondary" disabled={busy}>
                Simpan perubahan baris {rowNumber}
              </button>
              <button
                type="button"
                disabled={busy || !values.reviewed}
                onClick={() => void handleConfirm()}
              >
                Konfirmasi & bukukan baris {rowNumber}
              </button>
            </div>
          </fieldset>
        </form>
      )}
    </section>
  );
}

export function DraftEditor({ draftId }: { draftId: string }) {
  const { business, role } = useAuth();
  const client = useQueryClient();
  const draftQuery = useDraft(draftId);
  const draft = draftQuery.data;
  const evidence = useEvidenceFile(draft?.file_id);
  const products = useProducts("", 0, 100);
  useOcrJob(draft?.ocr_job_id);

  const [receiptNumberDraft, setReceiptNumberDraft] = useState<string | null>(
    null
  );
  const [receiptDateDraft, setReceiptDateDraft] = useState<string | null>(null);
  const [metaBusy, setMetaBusy] = useState(false);
  const [metaError, setMetaError] = useState("");
  const [metaNotice, setMetaNotice] = useState("");

  const receiptNumber =
    receiptNumberDraft ?? (draft?.receipt_number || "");
  const receiptDate = receiptDateDraft ?? (draft?.receipt_date || "");
  const activeProducts = (products.data?.items || []).filter((p) => p.active);

  async function saveMetadata(event: FormEvent) {
    event.preventDefault();
    if (!business || !draft) return;
    setMetaBusy(true);
    setMetaError("");
    setMetaNotice("");
    try {
      await api(
        `/businesses/${business.business_id}/transaction-drafts/${draft.id}`,
        {
          method: "PATCH",
          body: {
            expected_version: draft.version,
            receipt_number: receiptNumber.trim() || null,
            receipt_date: receiptDate.trim() || null,
          },
        }
      );
      setReceiptNumberDraft(null);
      setReceiptDateDraft(null);
      setMetaNotice("Informasi nota tersimpan.");
      await client.invalidateQueries({
        queryKey: ["transaction-draft", business.business_id, draftId],
      });
    } catch (failure) {
      setMetaError(
        failure instanceof Error
          ? failure.message
          : "Informasi nota belum tersimpan."
      );
    } finally {
      setMetaBusy(false);
    }
  }

  return (
    <QueryState
      loading={draftQuery.isPending || products.isPending}
      error={draftQuery.error || products.error}
      retry={() => {
        void draftQuery.refetch();
        void products.refetch();
      }}
    >
      {draft && (
        <div className="stack">
          <div className="page-heading">
            <div>
              <h1>Pemeriksaan draf nota</h1>
              <p className="muted">
                Status draf: <strong>{draft.status}</strong> · Periksa setiap baris
                dan pilih produk terdaftar sebelum membukukan ke stok.
              </p>
            </div>
          </div>

          {draft.duplicate_ids.length > 0 && (
            <div role="alert" className="notice warning">
              <p>
                [!] Peringatan duplikat nomor nota: Nomor nota{" "}
                <strong>{draft.receipt_number}</strong> sudah tercatat pada draf
                lain di usaha ini. Pastikan nota ini bukan pencatatan ulang.
              </p>
            </div>
          )}

          {draft.ocr_job_id && (
            <JobStatus jobId={draft.ocr_job_id} fileId={draft.file_id} />
          )}

          <div className="work-layout work-layout--aside">
            <div className="work-column">
              {evidence.data && (
                <section className="panel stack" aria-label="Berkas nota">
                  <EvidenceViewer
                    items={[evidence.data]}
                    title="Berkas bukti nota"
                  />
                </section>
              )}

              <section className="panel stack" aria-label="Metadata nota">
                <h2>Informasi nota</h2>
                {metaError && (
                  <p role="alert" className="notice error">
                    {metaError}
                  </p>
                )}
                {metaNotice && (
                  <p role="status" className="notice success">
                    {metaNotice}
                  </p>
                )}
                <form onSubmit={saveMetadata} className="stack">
                  <div className="split">
                    <FormField id="draft-receipt-number" label="Nomor nota">
                      <input
                        id="draft-receipt-number"
                        value={receiptNumber}
                        disabled={metaBusy || draft.status !== "pending"}
                        onChange={(event) =>
                          setReceiptNumberDraft(event.target.value)
                        }
                      />
                    </FormField>
                    <FormField id="draft-receipt-date" label="Tanggal nota">
                      <input
                        id="draft-receipt-date"
                        type="date"
                        value={receiptDate}
                        disabled={metaBusy || draft.status !== "pending"}
                        onChange={(event) =>
                          setReceiptDateDraft(event.target.value)
                        }
                      />
                    </FormField>
                  </div>
                  {draft.status === "pending" && (
                    <div>
                      <button
                        type="submit"
                        className="secondary"
                        disabled={metaBusy}
                      >
                        Simpan info nota
                      </button>
                    </div>
                  )}
                </form>
              </section>

              {draft.original_ocr && (
                <details className="disclosure" aria-label="Teks bacaan OCR mentah">
                  <summary>Teks bacaan OCR (hasil mesin)</summary>
                  <div className="stack">
                    <p className="hint">
                      [!] Hasil bacaan mesin · Belum diperiksa manusia
                    </p>
                    <pre className="ocr-text">{draft.original_ocr.raw_text}</pre>
                  </div>
                </details>
              )}
            </div>

            <div className="work-column">
              <section className="stack" aria-label="Baris transaksi draf">
                <h2>Baris transaksi draf</h2>
                {draft.lines.map((line, index) => (
                  <LineRowEditor
                    key={line.id}
                    draftId={draft.id}
                    line={line}
                    index={index}
                    products={activeProducts}
                    isOwner={role === "owner"}
                    onChanged={() => void draftQuery.refetch()}
                  />
                ))}
              </section>
            </div>
          </div>
        </div>
      )}
    </QueryState>
  );
}
