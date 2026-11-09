"use client";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FormField } from "@/components/form-field";
import { QueryState } from "@/components/query-state";
import type { Movement } from "@/features/inventory/api";
import type { Product } from "@/features/products/api";
import { useReversalRequests, type ReversalView } from "./api";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatTime } from "@/lib/format";
import { completeMutation, pendingMutations, prepareMutation, type PendingMutation } from "@/lib/idempotency";

function ReversalItem({ item, onDone }: { item: ReversalView; onDone: () => void }) {
  const { business, session, role } = useAuth();
  const client = useQueryClient();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const scopePrefix = `reversal-decision:${business?.business_id}:${item.id}:`;
  const [pending, setPending] = useState<PendingMutation | undefined>(() =>
    pendingMutations().find(value => value.scope.startsWith(scopePrefix))
  );
  const isSelf = item.user_id === session?.user.id;

  async function send(value: PendingMutation) {
    if (!business) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/businesses/${business.business_id}/reversal-requests/${item.id}/decisions`, {
        method: "POST", body: value.payload, idempotencyKey: value.id,
      });
      completeMutation(value.id);
      setPending(undefined);
      setNotice("Keputusan pembalikan tersimpan.");
      await client.invalidateQueries();
      onDone();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status < 500) {
        completeMutation(value.id);
        setPending(undefined);
      } else {
        setPending(value);
      }
      setError(failure instanceof Error ? failure.message : "Keputusan pembalikan belum berhasil.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: "approve" | "reject") {
    if (!business) return;
    if (decision === "reject" && !note.trim()) {
      setError("Alasan penolakan wajib diisi.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      const movement = await api<Movement>(`/businesses/${business.business_id}/movements/${item.original_movement_id}`);
      const product = await api<Product>(`/businesses/${business.business_id}/products/${movement.product_id}`);
      const scope = `reversal-decision:${business.business_id}:${item.id}:${decision}`;
      const value = prepareMutation(scope, {
        expected_request_version: item.version,
        expected_balance_version: product.balance_version,
        decision,
        note: note.trim(),
      });
      setPending(value);
      await send(value);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status < 500) {
        setError(failure.message);
      } else {
        setError(failure instanceof Error ? failure.message : "Keputusan pembalikan belum berhasil.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel stack">
      <div>
        <strong>Permintaan pembalikan #{item.id.slice(0, 8)}</strong>
        <p className="muted">Transaksi asli: {item.original_movement_id} · Diajukan {formatTime(item.created_at)} · Status: {item.status === "pending_review" ? "Menunggu tinjauan" : item.status === "resolved" ? "Disetujui" : "Ditolak"}</p>
      </div>
      <p>Alasan pengajuan: {item.reason}</p>
      {error && <p role="alert" className="notice error">{error}</p>}
      {notice && <p role="status" className="notice">{notice}</p>}
      {pending && role === "owner" && !isSelf && (
        <div className="notice">
          <p>Hasil keputusan belum pasti. Ulangi keputusan dengan isian dan nomor permintaan asli.</p>
          <button type="button" disabled={busy} onClick={() => void send(pending)}>Ulangi keputusan pembalikan asli</button>
        </div>
      )}

      {!pending && item.status === "pending_review" && role === "owner" && (
        isSelf ? (
          <div role="alert" className="notice warning">
            <p>Anda mengajukan permintaan pembalikan ini sendiri. Pemilik tidak dapat menyetujui permintaannya sendiri; gunakan akun pemilik lain atau minta staf yang mengajukan.</p>
          </div>
        ) : (
          <form onSubmit={(event: FormEvent) => event.preventDefault()} className="stack">
            <FormField id={`rev-note-${item.id}`} label="Catatan keputusan pembalikan" hint="Wajib diisi bila menolak permintaan.">
              <input id={`rev-note-${item.id}`} value={note} onChange={(event) => setNote(event.target.value)} />
            </FormField>
            <div className="actions">
              <button type="button" disabled={busy} onClick={() => void decide("approve")}>Setujui pembalikan</button>
              <button type="button" className="secondary" disabled={busy} onClick={() => void decide("reject")}>Tolak pembalikan</button>
            </div>
          </form>
        )
      )}
    </div>
  );
}

export function ReversalReview() {
  const reversals = useReversalRequests(0, 50);
  return (
    <section className="stack" aria-label="Antrean permintaan pembalikan">
      <h2>Permintaan pembalikan transaksi</h2>
      <QueryState
        loading={reversals.isPending}
        error={reversals.error}
        retry={() => void reversals.refetch()}
        empty={reversals.data?.total === 0 ? "Belum ada permintaan pembalikan transaksi." : undefined}
      >
        <div className="stack">
          {reversals.data?.items.map((item) => (
            <ReversalItem key={item.id} item={item} onDone={() => void reversals.refetch()} />
          ))}
        </div>
      </QueryState>
    </section>
  );
}
