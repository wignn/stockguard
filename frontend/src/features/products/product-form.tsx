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
  return (
    <form onSubmit={submit} className="stack">
      {error && <p role="alert" className="notice error">{error}</p>}
      <div className="form-grid">
        <FormField id="product-sku" label="Kode produk (SKU)">
          <input
            id="product-sku"
            required
            value={values.sku}
            onChange={(event) => setValues({ ...values, sku: event.target.value })}
          />
        </FormField>
        <FormField id="product-name" label="Nama produk">
          <input
            id="product-name"
            required
            value={values.name}
            onChange={(event) => setValues({ ...values, name: event.target.value })}
          />
        </FormField>
        <FormField id="product-unit" label="Satuan dasar">
          <input
            id="product-unit"
            required
            value={values.unit}
            disabled={!!product && product.balance_version > 0}
            onChange={(event) => setValues({ ...values, unit: event.target.value })}
          />
        </FormField>
        <FormField id="product-step_quantity" label="Langkah jumlah" hint="Pcs utuh: 1. Berat pecahan: misalnya 0.001.">
          <input
            id="product-step_quantity"
            required
            value={values.step_quantity}
            disabled={!!product && product.balance_version > 0}
            inputMode="decimal"
            onChange={(event) => setValues({ ...values, step_quantity: event.target.value })}
          />
        </FormField>
        <FormField id="product-cost_rupiah" label="Harga pokok per satuan (Rp)">
          <input
            id="product-cost_rupiah"
            required
            value={values.cost_rupiah}
            inputMode="decimal"
            onChange={(event) => setValues({ ...values, cost_rupiah: event.target.value })}
          />
        </FormField>
      </div>
      {product && product.balance_version > 0 && <p className="hint">Satuan dan langkah terkunci karena sudah ada transaksi.</p>}
      <div className="actions">
        <button disabled={busy}>{busy ? "Menyimpan…" : "Simpan produk"}</button>
      </div>
    </form>
  );
}
