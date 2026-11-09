import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Usaha saya" };

export default function WorkspacePage() {
  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>Usaha saya</h1>
          <p className="muted">Akun dan usaha aktif ditampilkan pada bilah atas sistem.</p>
        </div>
      </div>

      <div className="work-layout">
        <div className="work-column">
          <section className="panel stack" aria-label="Informasi operasional">
            <h2>Catatan dan pemeriksaan stok</h2>
            <p>Gunakan usaha aktif yang sesuai sebelum mencatat transaksi atau melakukan hitungan fisik.</p>
            <p className="muted">
              StokGuard menyimpan riwayat transaksi dan keputusan secara permanen (append-only) agar perbedaan stok dapat diperiksa secara objektif, bukan langsung dicurigai sebagai kecurangan.
            </p>
          </section>
        </div>

        <div className="work-column">
          <section className="panel stack" aria-label="Pintasan kerja usaha">
            <h2>Pintasan kerja</h2>
            <div className="actions">
              <Link className="button" href="/record">Catat transaksi baru</Link>
              <Link className="button secondary" href="/stocktakes">Mulai sesi opname</Link>
              <Link className="button secondary" href="/cases">Daftar kasus selisih</Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
