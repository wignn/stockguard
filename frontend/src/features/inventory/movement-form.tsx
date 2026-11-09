"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FormField } from "@/components/form-field";
import { QueryState } from "@/components/query-state";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatQuantity } from "@/lib/format";
import { completeMutation, pendingMutations, prepareMutation, type PendingMutation } from "@/lib/idempotency";
import { useProducts } from "@/features/products/api";
import type { components } from "@/lib/contracts";

type Command = components["schemas"]["MovementCommand"];
export const movementNames: Record<string, string> = { opening: "Saldo awal (masuk)", inbound: "Barang masuk", sale: "Penjualan (keluar)", damage: "Rusak (keluar)", customer_return: "Retur pelanggan (masuk)", supplier_return: "Retur pemasok (keluar)" };

export function MovementForm({ productId = "" }: { productId?: string }) {
  const { business, role } = useAuth();
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const products = useProducts(search.trim(), offset, 100);
  const client = useQueryClient();
  const scope = `movement:${business?.business_id}`;
  const [pending, setPending] = useState<PendingMutation | undefined>(() => typeof window === "undefined" ? undefined : pendingMutations().find((item) => item.scope === scope));
  const [selected, setSelected] = useState(productId);
  const [kind, setKind] = useState<Command["kind"]>("inbound");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const product = products.data?.items.find((item) => item.id === selected);
  const active = products.data?.items.filter((item) => item.active) || [];
  async function send(item: PendingMutation) {
    setBusy(true); setError(""); setSuccess("");
    try {
      await api(`/businesses/${business!.business_id}/movements`, { method: "POST", body: item.payload, idempotencyKey: item.id });
      completeMutation(item.id); setPending(undefined); setQuantity(""); setNote("");
      setSuccess("Transaksi tercatat."); await client.invalidateQueries();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status < 500) { completeMutation(item.id); setPending(undefined); }
      else setPending(item);
      setError(failure instanceof ApiError ? failure.message : "Hasil pencatatan belum pasti. Periksa riwayat atau ulangi permintaan asli di bawah.");
    } finally { setBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!product || !business) return;
    try {
      const item = prepareMutation(scope, { product_id: product.id, kind, quantity, note, occurred_at: new Date().toISOString(), expected_balance_version: product.balance_version } satisfies Command);
      setPending(item); await send(item);
    } catch (failure) { setError((failure as Error).message); }
  }
  return <><div className="stack"><FormField id="movement-search" label="Cari produk" hint="Cari nama atau SKU, lalu pilih hasil di bawah. Hanya produk aktif yang dapat dicatat."><input id="movement-search" type="search" value={search} disabled={busy || !!pending} onChange={(event) => { setSearch(event.target.value); setOffset(0); setSelected(""); }} /></FormField>
    {products.data && products.data.total > 100 && <div className="actions"><button type="button" className="secondary" disabled={offset === 0 || busy || !!pending} onClick={() => { setOffset(offset - 100); setSelected(""); }}>Produk sebelumnya</button><button type="button" className="secondary" disabled={offset + 100 >= products.data.total || busy || !!pending} onClick={() => { setOffset(offset + 100); setSelected(""); }}>Produk berikutnya</button></div>}
    </div><QueryState loading={products.isPending} error={products.error} retry={() => products.refetch()}>
    {search.trim() && active.length > 0 && <section className="stack" aria-label="Hasil pencarian produk">
      <p className="hint" role="status">{active.length} produk aktif pada halaman hasil ini. Pilih produk untuk melanjutkan.</p>
      <ul className="search-results">{active.map(item => <li key={item.id}><button type="button" className="secondary" aria-label={`Pilih ${item.name} (${item.sku})`} aria-pressed={selected === item.id} disabled={busy || !!pending} onClick={() => setSelected(item.id)}><span><strong>{item.name}</strong> <small>({item.sku})</small></span><span>{selected === item.id ? "Dipilih" : "Pilih"}</span></button></li>)}</ul>
    </section>}
    {pending && <section className="notice" aria-label="Permintaan belum pasti"><p>Permintaan tersimpan dengan jumlah {(pending.payload as Command).quantity}. Pengulangan memakai isian dan nomor permintaan asli.</p><button type="button" disabled={busy} onClick={() => send(pending)}>Ulangi permintaan asli</button> <Link href="/movements">Periksa riwayat</Link></section>}
    {!active.length ? <div className="notice"><p>{search.trim() ? `Tidak ada produk aktif yang cocok dengan “${search.trim()}”. Ubah pencarian atau periksa status produk pada usaha aktif.` : "Belum ada produk aktif. Tambahkan produk sebelum mencatat transaksi."}</p><Link href="/products">Buka produk</Link></div> : <form onSubmit={submit} className="form-width">
      {error && <p role="alert" className="notice error">{error}</p>}{success && <p role="status" className="notice">{success}</p>}
      <fieldset disabled={busy || !!pending}>
        <FormField id="movement-product" label="Produk"><select id="movement-product" required value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">Pilih produk</option>{active.map((item) => <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>)}</select></FormField>
        <FormField id="movement-kind" label="Jenis transaksi"><select id="movement-kind" value={kind} onChange={(event) => setKind(event.target.value as Command["kind"])}>{Object.entries(movementNames).filter(([key]) => key !== "opening" || role === "owner").map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></FormField>
        <FormField id="movement-quantity" label="Jumlah" hint={product ? `Satuan ${product.unit}. Langkah ${product.step_quantity}.` : "Pilih produk untuk melihat satuan."}><input id="movement-quantity" type="number" inputMode="decimal" min={product?.step_quantity || "0.001"} step={product?.step_quantity || "0.001"} value={quantity} onChange={(event) => setQuantity(event.target.value)} required /></FormField>
        <FormField id="movement-note" label="Catatan transaksi" hint="Jelaskan asal barang, penjualan, atau alasan barang keluar."><textarea id="movement-note" required value={note} onChange={(event) => setNote(event.target.value)} /></FormField>
        {product && <p className="notice">Saldo sistem saat dimuat: {formatQuantity(product.balance_quantity)} {product.unit}. Transaksi: {movementNames[kind]}, jumlah {quantity || "0"} {product.unit}. Saldo akhir ditentukan server saat pencatatan.</p>}
        <button disabled={!product || busy}>{busy ? "Mencatat…" : "Catat transaksi"}</button>
      </fieldset>
    </form>}
  </QueryState></>;
}
