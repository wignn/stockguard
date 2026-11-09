"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FormField } from "@/components/form-field";
import { QueryState } from "@/components/query-state";
import { useCases } from "@/features/cases/api";
import { caseStatusNames } from "@/features/cases/case-detail";
import { useProducts } from "@/features/products/api";
import { useStocktakes, type Stocktake } from "@/features/stocktakes/api";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatQuantity, formatRupiah, formatTime } from "@/lib/format";

export default function StocktakesPage() {
  const { business } = useAuth();
  const router = useRouter();
  const client = useQueryClient();
  const products = useProducts("", 0, 100);
  const stocktakes = useStocktakes(0, 25);
  const cases = useCases(0, 25);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const activeProducts = products.data?.items.filter((item) => item.active) || [];
  const productMap = new Map((products.data?.items || []).map((item) => [item.id, item]));

  async function start(event: FormEvent) {
    event.preventDefault();
    if (!business || !selectedProduct) return;
    setBusy(true); setError("");
    try {
      const created = await api<Stocktake>(`/businesses/${business.business_id}/stocktakes`, {
        method: "POST",
        body: { product_id: selectedProduct },
      });
      await client.invalidateQueries();
      router.push(`/stocktakes/${created.id}`);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Sesi opname belum dapat dimulai.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>Opname dan kasus selisih</h1>
          <p className="muted">Mulai sesi hitung fisik 15 menit atau lanjutkan pemeriksaan selisih yang masih terbuka.</p>
        </div>
      </div>

      {error && <p role="alert" className="notice error">{error}</p>}

      <div className="work-layout">
        <div className="work-column">
          <section className="panel stack" aria-label="Mulai opname baru">
            <h2>Mulai sesi opname</h2>
            <QueryState loading={products.isPending} error={products.error} retry={() => void products.refetch()}>
              {!activeProducts.length ? (
                <p className="muted">Belum ada produk aktif. <Link href="/products">Buka produk</Link></p>
              ) : (
                <form onSubmit={start} className="stack">
                  <FormField id="stocktake-product" label="Produk untuk dihitung">
                    <select id="stocktake-product" required value={selectedProduct} onChange={(event) => setSelectedProduct(event.target.value)}>
                      <option value="">Pilih produk</option>
                      {activeProducts.map((item) => (
                        <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>
                      ))}
                    </select>
                  </FormField>
                  <button type="submit" disabled={!selectedProduct || busy}>{busy ? "Memulai…" : "Mulai sesi opname"}</button>
                </form>
              )}
            </QueryState>
          </section>
        </div>

        <div className="work-column">
          <section className="panel stack" aria-label="Daftar kasus investigasi">
            <h2>Kasus selisih</h2>
            <QueryState
              loading={cases.isPending}
              error={cases.error}
              retry={() => void cases.refetch()}
              empty={cases.data?.total === 0 ? "Belum ada kasus selisih." : undefined}
            >
              <div className="table-wrap responsive-table" tabIndex={0} role="region" aria-label="Gulir kasus selisih">
                <table>
                  <caption className="sr-only">Daftar kasus selisih stok</caption>
                  <thead>
                    <tr>
                      <th>Produk</th>
                      <th>Selisih</th>
                      <th>Perkiraan nilai</th>
                      <th>Status</th>
                      <th>Tindakan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.data?.items.map((item) => {
                      const prod = productMap.get(item.product_id);
                      return (
                        <tr key={item.id}>
                          <td>{prod ? `${prod.sku} · ${prod.name}` : item.product_id.slice(0, 8)}</td>
                          <td data-label="Selisih fisik − sistem">{formatQuantity(item.difference_quantity)} {prod?.unit || ""}</td>
                          <td data-label="Perkiraan nilai">{formatRupiah(item.estimated_value_rupiah)}</td>
                          <td data-label="Status">{caseStatusNames[item.status] || item.status}</td>
                          <td><Link href={`/cases/${item.id}`}>Buka kasus {prod?.name || item.id.slice(0, 6)}</Link></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </QueryState>
          </section>
        </div>
      </div>

      <details className="disclosure">
        <summary>Sesi opname terakhir</summary>
        <section className="stack" aria-label="Riwayat sesi opname">
          <QueryState
            loading={stocktakes.isPending}
            error={stocktakes.error}
            retry={() => void stocktakes.refetch()}
            empty={stocktakes.data?.total === 0 ? "Belum ada sesi opname." : undefined}
          >
            <div className="table-wrap responsive-table" tabIndex={0} role="region" aria-label="Gulir riwayat sesi opname">
              <table>
                <caption className="sr-only">Riwayat sesi opname</caption>
                <thead>
                  <tr>
                    <th>Waktu mulai</th>
                    <th>Produk</th>
                    <th>Saldo dasar</th>
                    <th>Fisik</th>
                    <th>Selisih</th>
                    <th>Status</th>
                    <th>Tindakan</th>
                  </tr>
                </thead>
                <tbody>
                  {stocktakes.data?.items.map((item) => {
                    const prod = productMap.get(item.product_id);
                    return (
                      <tr key={item.id}>
                        <td>{formatTime(item.started_at)}</td>
                        <td data-label="Produk">{prod ? `${prod.sku} · ${prod.name}` : item.product_id.slice(0, 8)}</td>
                        <td data-label="Saldo dasar">{formatQuantity(item.baseline_quantity)}</td>
                        <td data-label="Fisik terhitung">{item.counted_quantity !== null ? formatQuantity(item.counted_quantity) : "Belum dihitung"}</td>
                        <td data-label="Selisih">{item.difference_quantity !== null ? formatQuantity(item.difference_quantity) : "Belum dihitung"}</td>
                        <td data-label="Status">{item.status}</td>
                        <td><Link href={`/stocktakes/${item.id}`} aria-label={`Lihat sesi ${prod?.name || item.id.slice(0, 8)} dimulai ${formatTime(item.started_at)}`}>Lihat sesi</Link></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </QueryState>
        </section>
      </details>
    </div>
  );
}
