"use client";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { FormField } from "@/components/form-field";
import type { Product } from "./api";

export function ProductForm({ product, onDone }: { product?: Product; onDone: () => void }) {
  const { business } = useAuth();
  const client = useQueryClient();
  const [values, setValues] = useState({ sku: product?.sku || "", name: product?.name || "", unit: product?.unit || "Pcs", step_quantity: product?.step_quantity || "1", cost_rupiah: product?.cost_rupiah || "0" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await api(`/businesses/${business!.business_id}/products${product ? `/${product.id}` : ""}`, { method: product ? "PATCH" : "POST", body: product ? { expected_version: product.version, sku: values.sku, name: values.name, cost_rupiah: values.cost_rupiah, ...(product.balance_version === 0 ? { unit: values.unit, step_quantity: values.step_quantity } : {}) } : values }); await client.invalidateQueries(); onDone(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Produk belum tersimpan."); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="form-width">{error && <p role="alert" className="notice error">{error}</p>}{Object.entries({ sku: "Kode produk (SKU)", name: "Nama produk", unit: "Satuan dasar", step_quantity: "Langkah jumlah", cost_rupiah: "Harga pokok per satuan (Rp)" }).map(([key, label]) => <FormField key={key} id={`product-${key}`} label={label} hint={key === "step_quantity" ? "Pcs utuh: 1. Berat pecahan: misalnya 0.001." : undefined}><input id={`product-${key}`} required value={values[key as keyof typeof values]} onChange={(event) => setValues({ ...values, [key]: event.target.value })} disabled={!!product && product.balance_version > 0 && ["unit", "step_quantity"].includes(key)} inputMode={["step_quantity", "cost_rupiah"].includes(key) ? "decimal" : "text"} /></FormField>)}{product && product.balance_version > 0 && <p className="hint">Satuan dan langkah terkunci karena sudah ada transaksi.</p>}<button disabled={busy}>{busy ? "Menyimpan…" : "Simpan produk"}</button></form>;
}
