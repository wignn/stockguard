"use client";
import { useState, type FormEvent } from "react";
import { useMovements, type Movement } from "./api";
import { movementNames } from "./movement-form";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { Product } from "@/features/products/api";
import { Dialog } from "@/components/dialog";
import { FormField } from "@/components/form-field";
import { QueryState } from "@/components/query-state";
import { formatQuantity, formatTime } from "@/lib/format";

function ReversalForm({ movement }: { movement: Movement }) {
  const { business } = useAuth();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const product = await api<Product>(`/businesses/${business!.business_id}/products/${movement.product_id}`);
      await api(`/businesses/${business!.business_id}/movements/${movement.id}/reversal-requests`, { method: "POST", body: { reason, expected_balance_version: product.balance_version } });
      setDone(true);
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  return <><p>Transaksi asli tetap tersimpan. Pemilik lain perlu meninjau permintaan; saldo belum berubah saat pengajuan.</p><dl><dt>Transaksi asli</dt><dd>{movement.id}</dd><dt>Jenis dan jumlah</dt><dd>{movementNames[movement.kind] || movement.kind}: {formatQuantity(movement.quantity)}</dd><dt>Catatan</dt><dd>{movement.note}</dd></dl>{done ? <p role="status">Permintaan pembalikan diajukan.</p> : <form onSubmit={submit}>{error && <p role="alert" className="notice error">{error}</p>}<FormField id="reversal-reason" label="Alasan pembalikan"><textarea id="reversal-reason" required value={reason} onChange={(event) => setReason(event.target.value)} /></FormField><button disabled={busy}>{busy ? "Mengajukan…" : "Kirim permintaan pembalikan"}</button></form>}</>;
}

export function MovementList() {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Movement | null>(null);
  const movements = useMovements(offset);
  return <><h1>Riwayat transaksi</h1><p className="muted">Transaksi tidak dapat diubah atau dihapus. Ajukan pembalikan jika pencatatan keliru.</p><QueryState loading={movements.isPending} error={movements.error} retry={() => movements.refetch()} empty={movements.data?.total === 0 ? "Belum ada transaksi. Buka Catat transaksi untuk mencatat barang masuk atau keluar." : undefined}>
    <div className="table-wrap responsive-table"><table><caption className="sr-only">Transaksi yang telah tercatat</caption><thead><tr><th>Waktu transaksi</th><th>Jenis</th><th>Jumlah</th><th>Saldo sesudah</th><th>Catatan</th><th>Tindakan</th></tr></thead><tbody>{movements.data?.items.map((movement) => <tr key={movement.id}><td>{formatTime(movement.occurred_at)}</td><td data-label="Jenis">{movementNames[movement.kind] || movement.kind}</td><td data-label="Jumlah">{formatQuantity(movement.quantity)}</td><td data-label="Saldo sesudah">{formatQuantity(movement.balance_quantity)}</td><td data-label="Catatan">{movement.note}</td><td>{movement.kind !== "reversal" && <button className="secondary" aria-label={`Ajukan pembalikan ${movement.note}`} onClick={() => setSelected(movement)}>Ajukan pembalikan</button>}</td></tr>)}</tbody></table></div>
    <div className="actions"><button className="secondary" disabled={offset === 0} onClick={() => setOffset(offset - 25)}>Sebelumnya</button><span>{movements.data?.total || 0} transaksi</span><button className="secondary" disabled={offset + 25 >= (movements.data?.total || 0)} onClick={() => setOffset(offset + 25)}>Berikutnya</button></div>
  </QueryState><Dialog open={!!selected} title="Ajukan pembalikan" onClose={() => setSelected(null)}>{selected && <ReversalForm key={selected.id} movement={selected} />}</Dialog></>;
}
