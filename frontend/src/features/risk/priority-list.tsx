"use client";
import Link from "next/link";
import { QueryState } from "@/components/query-state";
import { useCases, caseStatusNames } from "@/features/cases/api";
import { useDashboard, type RiskAssessment } from "./api";
import { formatTime } from "@/lib/format";

const riskLabels: Record<RiskAssessment["priority"], string> = {
  high: "[!] Tinggi",
  medium: "[~] Sedang",
  low: "[✓] Rendah",
  insufficient: "[i] Histori belum cukup",
};

export function PriorityList() {
  const dashboard = useDashboard(0, 50);
  const cases = useCases(0, 50);

  const items = dashboard.data?.products.items || [];
  const activeProductsCount = dashboard.data?.active_products ?? 0;
  const unresolvedCasesCount = dashboard.data?.unresolved_cases ?? 0;
  const highPriorityCount = dashboard.data?.high_priority_products ?? 0;
  const unresolvedCases = (cases.data?.items || []).filter(
    (item) => item.status !== "resolved"
  );

  const ruleVersion = items[0]?.risk.rule_version || "rules-v1";

  return (
    <QueryState
      loading={dashboard.isPending || cases.isPending}
      error={dashboard.error || cases.error}
      retry={() => {
        void dashboard.refetch();
        void cases.refetch();
      }}
    >
      <div className="stack">
        <section
          className="stat-grid"
          aria-label="Ringkasan usaha"
        >
          <article className="panel stat-tile">
            <span className="muted">Produk aktif dipantau</span>
            <strong className="stat-number">{activeProductsCount}</strong>
            <span className="muted">
              Populasi produk aktif usaha ini
            </span>
          </article>
          <article className="panel stat-tile">
            <span className="muted">Prioritas cek fisik tinggi</span>
            <strong className="stat-number">{highPriorityCount}</strong>
            <span className="muted">
              Berdasarkan riwayat selisih & koreksi tanpa bukti
            </span>
          </article>
          <article className="panel stat-tile">
            <span className="muted">Kasus selisih belum selesai</span>
            <strong className="stat-number">{unresolvedCasesCount}</strong>
            <span className="muted">
              Menunggu investigasi staf, hitung ulang, atau keputusan pemilik
            </span>
          </article>
        </section>

        <div className="actions" role="group" aria-label="Pekerjaan stok"><Link className="button" href="/record">Catat transaksi</Link><Link className="button secondary" href="/record">Periksa draf nota</Link></div>

        <section className="panel stack" aria-label="Prioritas cek fisik produk">
          <div className="page-heading">
            <div>
              <h2>Urutan prioritas cek fisik</h2>
              <p className="muted">
                Dihitung dengan aturan deterministik{" "}
                <strong>{ruleVersion}</strong> pada jendela waktu{" "}
                <strong>30 hari terakhir</strong> tanpa skor persentase buatan.
              </p>
            </div>
            <Link className="button secondary" href="/stocktakes">
              Mulai cek fisik
            </Link>
          </div>

          {items.length === 0 ? (
            <div className="notice">
              <p>Belum ada produk aktif pada usaha ini.</p>
              <Link className="button secondary" href="/products">
                Buka katalog produk
              </Link>
            </div>
          ) : (
            <div className="table-wrap responsive-table" tabIndex={0} role="region" aria-label="Gulir daftar prioritas cek fisik">
              <table>
                <caption className="sr-only">
                  Daftar prioritas cek fisik produk
                </caption>
                <thead>
                  <tr>
                    <th>Produk</th>
                    <th>Tingkat prioritas</th>
                    <th>Alasan aturan</th>
                    <th>Kasus / koreksi</th>
                    <th>Tindakan</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(({ product, risk }) => (
                    <tr key={product.id}>
                      <td>
                        <strong>{product.name}</strong>
                        <div className="muted">
                          {product.sku} · Satuan {product.unit}
                        </div>
                      </td>
                      <td data-label="Prioritas cek fisik">
                        <span className={`badge risk-${risk.priority}`}>
                          {riskLabels[risk.priority]}
                        </span>
                      </td>
                      <td data-label="Alasan pemeriksaan">
                        <ul className="reason-list">
                          {risk.reasons.map((reason, idx) => (
                            <li key={idx}>{reason}</li>
                          ))}
                        </ul>
                      </td>
                      <td data-label="Riwayat 30 hari">
                        {risk.case_count} kasus · {risk.missing_evidence_corrections} koreksi tanpa bukti
                      </td>
                      <td>
                        <Link className="button secondary" href="/stocktakes" aria-label={`Buka opname untuk memilih produk ${product.name}`}>
                          Buka opname
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section
          className="panel stack"
          aria-label="Kasus selisih yang masih berjalan"
        >
          <div className="page-heading">
            <div>
              <h2>Kasus selisih yang perlu ditindaklanjuti</h2>
              <p className="muted">
                Menampilkan kasus dengan status investigasi, menunggu tinjauan pemilik,
                atau wajib hitung ulang.
              </p>
            </div>
            <Link className="button secondary" href="/cases">
              Semua kasus
            </Link>
          </div>
          {unresolvedCases.length === 0 ? (
            <p className="muted">
              {unresolvedCasesCount === 0 ? "Tidak ada kasus selisih yang sedang berjalan." : "Tidak ada kasus terbuka pada 50 riwayat yang dimuat. Buka Semua kasus untuk menelusuri riwayat lainnya."}
            </p>
          ) : (
            <div className="table-wrap responsive-table" tabIndex={0} role="region" aria-label="Gulir kasus selisih berjalan">
              <table>
                <caption className="sr-only">
                  Kasus selisih yang belum selesai
                </caption>
                <thead>
                  <tr>
                    <th>Selisih (fisik − sistem)</th>
                    <th>Status</th>
                    <th>Dibuka</th>
                    <th>Tindakan</th>
                  </tr>
                </thead>
                <tbody>
                  {unresolvedCases.map((item) => (
                    <tr key={item.id}>
                      <td className="number" data-label="Selisih fisik − sistem">{item.difference_quantity}</td>
                      <td data-label="Status">{caseStatusNames[item.status] || item.status}</td>
                      <td data-label="Dibuka">{formatTime(item.created_at)}</td>
                      <td>
                        <Link
                          className="button secondary"
                          href={`/cases/${item.id}`}
                          aria-label={`Buka kasus ${item.id.slice(0, 8)}`}
                        >
                          Buka kasus
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </QueryState>
  );
}
