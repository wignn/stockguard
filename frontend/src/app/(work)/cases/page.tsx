"use client";
import Link from "next/link";
import { useState } from "react";
import { QueryState } from "@/components/query-state";
import { caseStatusNames, useCases } from "@/features/cases/api";
import { useProducts } from "@/features/products/api";
import { formatQuantity, formatRupiah } from "@/lib/format";

export default function CasesPage() {
  const [offset, setOffset] = useState(0);
  const cases = useCases(offset, 25);
  const products = useProducts("", 0, 100);
  const productMap = new Map((products.data?.items || []).map(item => [item.id, item]));

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>Kasus selisih</h1>
          <p className="muted">Telusuri perbedaan hasil opname, lengkapi temuan, lalu ajukan kepada pemilik.</p>
        </div>
      </div>
      <QueryState
        loading={cases.isPending || products.isPending}
        error={cases.error || products.error}
        retry={() => { void cases.refetch(); void products.refetch(); }}
        empty={!cases.data?.items.length ? "Belum ada kasus selisih. Kasus dibuat ketika hasil opname berbeda dari stok buku." : undefined}
      >
        <div className="table-wrap responsive-table">
          <table>
            <caption className="sr-only">Daftar kasus selisih</caption>
            <thead><tr><th>Produk</th><th>Selisih</th><th>Perkiraan nilai</th><th>Status</th><th>Tindakan</th></tr></thead>
            <tbody>{cases.data?.items.map(item => {
              const product = productMap.get(item.product_id);
              return <tr key={item.id}>
                <td><strong>{product?.name || item.product_id}</strong>{product && <div className="muted">{product.sku}</div>}</td>
                <td data-label="Selisih fisik − sistem">{formatQuantity(item.difference_quantity)} {product?.unit || ""}</td>
                <td data-label="Perkiraan nilai">{formatRupiah(item.estimated_value_rupiah)}</td>
                <td data-label="Status"><span className="badge">{caseStatusNames[item.status] || item.status}</span></td>
                <td><Link href={`/cases/${item.id}`}>Buka kasus {product?.name || item.id.slice(0, 6)}</Link></td>
              </tr>;
            })}</tbody>
          </table>
        </div>
      </QueryState>
      <div className="actions" role="group" aria-label="Halaman kasus">
        <button className="button secondary" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 25))}>Kasus sebelumnya</button>
        <span className="muted">Halaman {Math.floor(offset / 25) + 1}</span>
        <button className="button secondary" disabled={!cases.data || offset + 25 >= cases.data.total} onClick={() => setOffset(value => value + 25)}>Kasus berikutnya</button>
      </div>
    </div>
  );
}
