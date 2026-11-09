"use client";
import Link from "next/link";
import { QueryState } from "@/components/query-state";
import { useCases } from "@/features/cases/api";
import { caseStatusNames } from "@/features/cases/case-detail";
import { ReversalReview } from "@/features/cases/reversal-review";
import { useProducts } from "@/features/products/api";
import { formatQuantity, formatRupiah } from "@/lib/format";

export default function ReviewPage() {
  const cases = useCases(0, 50);
  const products = useProducts("", 0, 100);
  const productMap = new Map((products.data?.items || []).map((item) => [item.id, item]));
  const openCases = cases.data?.items.filter((item) => item.status !== "resolved") || [];

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>Tinjauan pemilik</h1>
          <p className="muted">Periksa antrean pengajuan kasus selisih dan permintaan pembalikan transaksi secara terpisah.</p>
        </div>
      </div>

      <section className="stack" aria-label="Antrean kasus selisih">
        <h2>Antrean kasus selisih</h2>
        <QueryState
          loading={cases.isPending || products.isPending}
          error={cases.error || products.error}
          retry={() => { void cases.refetch(); void products.refetch(); }}
          empty={!openCases.length ? "Tidak ada kasus selisih yang menunggu keputusan atau pemeriksaan." : undefined}
        >
          <div className="table-wrap">
            <table>
              <caption className="sr-only">Antrean kasus selisih</caption>
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
                {openCases.map((item) => {
                  const prod = productMap.get(item.product_id);
                  return (
                    <tr key={item.id}>
                      <td>{prod ? `${prod.sku} · ${prod.name}` : item.product_id.slice(0, 8)}</td>
                      <td>{formatQuantity(item.difference_quantity)} {prod?.unit || ""}</td>
                      <td>{formatRupiah(item.estimated_value_rupiah)}</td>
                      <td>{caseStatusNames[item.status] || item.status}</td>
                      <td>
                        <Link href={`/cases/${item.id}`}>Tinjau kasus {prod?.name || item.id.slice(0, 6)}</Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </QueryState>
      </section>

      <ReversalReview />
    </div>
  );
}
