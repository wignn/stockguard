"use client";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FormField } from "@/components/form-field";
import { movementNames } from "@/features/inventory/movement-form";
import type { Product } from "@/features/products/api";
import type { CaseView } from "./api";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatQuantity } from "@/lib/format";

export const causeNames: Record<string, string> = {
  unrecorded_transaction: "Transaksi belum dicatat",
  damage_return: "Barang rusak atau retur belum dicatat",
  miscount: "Kekeliruan hitung fisik",
  unknown: "Penyebab belum teridentifikasi",
};

export const resolutionNames: Record<string, string> = {
  movement: "Catat transaksi yang terlupa",
  adjustment: "Koreksi penyesuaian stok",
  no_movement: "Tutup selisih tanpa perubahan stok (hitung cocok)",
};

export function SubmissionForm({ caseItem, product, onDone }: { caseItem: CaseView; product: Product; onDone: () => void }) {
  const { business } = useAuth();
  const client = useQueryClient();
  const evidenceIds = (caseItem.evidence || []).map(item => item.id);
  const isZeroDiff = caseItem.difference_quantity === "0";
  const [cause, setCause] = useState(isZeroDiff ? "miscount" : "unrecorded_transaction");
  const [resolutionKind, setResolutionKind] = useState(isZeroDiff ? "no_movement" : "movement");
  const [movementKind, setMovementKind] = useState(caseItem.difference_quantity.startsWith("-") ? "sale" : "inbound");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [missingEvidenceReason, setMissingEvidenceReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!business) return;
    setBusy(true); setError("");
    try {
      await api(`/businesses/${business.business_id}/cases/${caseItem.id}/submissions`, {
        method: "POST",
        body: {
          expected_case_version: caseItem.version,
          stocktake_id: caseItem.latest_stocktake_id,
          cause,
          resolution_kind: resolutionKind,
          quantity: resolutionKind === "no_movement" ? "0" : quantity.trim(),
          movement_kind: resolutionKind === "movement" ? movementKind : null,
          occurred_at: new Date().toISOString(),
          note: note.trim(),
          missing_evidence_reason: resolutionKind === "no_movement" || evidenceIds.length ? "" : missingEvidenceReason.trim(),
          evidence_ids: evidenceIds,
        },
      });
      await client.invalidateQueries();
      onDone();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Pengajuan belum dapat dikirim.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="panel form-width stack">
      <h2>Ajukan usulan penyelesaian</h2>
      <p className="muted">
        Selisih opname terbaru: <strong>{formatQuantity(caseItem.difference_quantity)} {product.unit}</strong>. Pilih satu tindak lanjut yang menjelaskan seluruh selisih tersebut.
      </p>
      {error && <p role="alert" className="notice error">{error}</p>}

      <FormField id="sub-cause" label="Kategori penyebab">
        <select id="sub-cause" value={cause} onChange={(event) => setCause(event.target.value)}>
          {Object.entries(causeNames).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </FormField>

      <FormField id="sub-resolution" label="Jenis tindak lanjut">
        <select
          id="sub-resolution"
          value={resolutionKind}
          onChange={(event) => {
            const next = event.target.value;
            setResolutionKind(next);
            if (next === "no_movement") setCause("miscount");
          }}
        >
          {Object.entries(resolutionNames).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </FormField>

      {resolutionKind === "movement" && (
        <FormField id="sub-movement-kind" label="Jenis transaksi terlupa">
          <select id="sub-movement-kind" value={movementKind} onChange={(event) => setMovementKind(event.target.value)}>
            {Object.entries(movementNames)
              .filter(([key]) => key !== "opening")
              .map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
          </select>
        </FormField>
      )}

      {resolutionKind !== "no_movement" && (
        <FormField id="sub-quantity" label="Jumlah usulan" hint={`Satuan ${product.unit}. Langkah ${product.step_quantity}. Masukkan jumlah positif yang sesuai besarnya selisih.`}>
          <input
            id="sub-quantity"
            type="number"
            inputMode="decimal"
            min={product.step_quantity}
            step={product.step_quantity}
            required
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </FormField>
      )}

      <FormField id="sub-note" label="Catatan pengajuan">
        <textarea id="sub-note" required value={note} onChange={(event) => setNote(event.target.value)} />
      </FormField>

      {evidenceIds.length > 0 && <p className="muted">{evidenceIds.length} foto bukti kasus disertakan pada pengajuan ini.</p>}
      {resolutionKind !== "no_movement" && evidenceIds.length === 0 && (
        <FormField id="sub-missing-evidence" label="Alasan tanpa lampiran bukti" hint="Wajib diisi bila tidak melampirkan foto bukti pada pengajuan ini.">
          <input id="sub-missing-evidence" required value={missingEvidenceReason} onChange={(event) => setMissingEvidenceReason(event.target.value)} />
        </FormField>
      )}

      <button type="submit" disabled={busy}>{busy ? "Mengirim…" : "Kirim pengajuan ke pemilik"}</button>
    </form>
  );
}
