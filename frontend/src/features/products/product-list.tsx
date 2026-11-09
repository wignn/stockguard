"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useProducts, type Product } from "./api";
import { ProductForm } from "./product-form";
import { Dialog } from "@/components/dialog";
import { QueryState } from "@/components/query-state";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { formatQuantity, formatRupiah } from "@/lib/format";

export function ProductList() {
  const { business, role } = useAuth();
  const client = useQueryClient();
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [edit, setEdit] = useState<Product | "new" | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const products = useProducts(q, offset);
  async function toggle(product: Product) {
    setBusy(true); setError("");
    try { await api(`/businesses/${business!.business_id}/products/${product.id}`, { method: "PATCH", body: { expected_version: product.version, active: !product.active } }); await client.invalidateQueries(); }
    catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  return <><div className="page-heading"><div><h1>Produk</h1><p className="muted">Satuan dasar dan saldo dari transaksi yang sudah tercatat.</p></div>{role === "owner" && <button onClick={() => setEdit("new")}>Tambah produk</button>}</div>
    <div className="search-toolbar"><label htmlFor="product-search">Cari nama atau SKU</label><input id="product-search" type="search" value={q} onChange={(event) => { setQ(event.target.value); setOffset(0); }} /></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    <QueryState loading={products.isPending} error={products.error} retry={() => products.refetch()} empty={products.data?.total === 0 ? "Belum ada produk yang cocok. Pemilik dapat menambahkan produk atau mengubah pencarian." : undefined}>
      <div className="table-wrap responsive-table" tabIndex={0} role="region" aria-label="Gulir katalog produk"><table><caption className="sr-only">Katalog produk dan saldo sistem</caption><thead><tr><th>Produk</th><th>Saldo sistem</th><th>Harga pokok</th><th>Status</th>{role === "owner" && <th>Tindakan</th>}</tr></thead><tbody>{products.data?.items.map((product) => <tr key={product.id}><td><strong>{product.name}</strong><br /><small className="muted">{product.sku}</small></td><td data-label="Saldo sistem"><strong>{formatQuantity(product.balance_quantity)}</strong> {product.unit}</td><td data-label="Harga pokok">{formatRupiah(product.cost_rupiah)}</td><td data-label="Status">{product.active ? "Aktif" : "Nonaktif"}</td>{role === "owner" && <td><div className="actions"><button className="secondary" aria-label={`Ubah ${product.name}`} onClick={() => setEdit(product)}>Ubah</button><button className="secondary" disabled={busy} aria-label={`${product.active ? "Nonaktifkan" : "Aktifkan"} ${product.name}`} onClick={() => toggle(product)}>{product.active ? "Nonaktifkan" : "Aktifkan"}</button></div></td>}</tr>)}</tbody></table></div>
      <div className="actions"><button className="secondary" disabled={offset === 0} onClick={() => setOffset(offset - 25)}>Sebelumnya</button><span>{products.data?.total || 0} produk</span><button className="secondary" disabled={offset + 25 >= (products.data?.total || 0)} onClick={() => setOffset(offset + 25)}>Berikutnya</button></div>
    </QueryState>
    <Dialog open={edit !== null} title={edit === "new" ? "Tambah produk" : "Ubah produk"} onClose={() => setEdit(null)}>{edit && <ProductForm key={edit === "new" ? "new" : edit.id} product={edit === "new" ? undefined : edit} onDone={() => setEdit(null)} />}</Dialog>
  </>;
}
