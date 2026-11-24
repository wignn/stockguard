import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "StokGuard - Rekonsiliasi & Audit Stok Fisik UMKM",
  description:
    "Sistem rekonsiliasi stok fisik dan pembukuan append-only untuk UMKM. Sandingkan transaksi harian dengan hitungan fisik, verifikasi nota via OCR, dan audit selisih secara transparan.",
};

export default function HomePage() {
  return (
    <>
      <header className="landing-nav" role="banner">
        <Link href="/" className="wordmark" aria-label="Beranda StokGuard">
          Stok<span>Guard</span>
        </Link>
        <nav className="landing-nav-links" aria-label="Navigasi umum">
          <a href="#fitur">Keunggulan</a>
          <a href="#alur-kerja">Alur Kerja</a>
          <a href="#perbandingan">Perbandingan</a>
        </nav>
        <div>
          <Link href="/login" className="button">
            Masuk ke Aplikasi
          </Link>
        </div>
      </header>

      <main className="landing-container">
        {/* Hero Section */}
        <section className="landing-hero" aria-label="Pengenalan StokGuard">
          <div className="badge">Sistem Rekonsiliasi & Audit Stok UMKM</div>
          <h1>Kendalikan stok fisik dan transaksi tanpa selisih yang tersembunyi.</h1>
          <p>
            Sandingkan catatan keluar-masuk barang dengan hitungan fisik berkala.
            Dilengkapi pembacaan bukti nota berbasis OCR lokal, buku besar append-only
            anti-manipulasi, dan alur investigasi selisih dengan persetujuan pemilik usaha.
          </p>
          <div className="actions">
            <Link href="/login" className="button">
              Masuk ke Aplikasi
            </Link>
            <a href="#alur-kerja" className="button secondary">
              Pelajari Alur Kerja
            </a>
          </div>
        </section>

        {/* 3 Langkah Alur Kerja */}
        <section id="alur-kerja" className="landing-section" aria-label="Alur kerja rekonsiliasi">
          <h2>Tiga langkah rekonsiliasi stok terstruktur</h2>
          <p className="muted">
            Memastikan setiap pergerakan barang dapat dipertanggungjawabkan dan selisih
            diselesaikan bersama.
          </p>

          <div className="landing-grid">
            <article className="landing-card">
              <span className="landing-step-num">Langkah 1</span>
              <h3>Pencatatan & Nota OCR</h3>
              <p>
                Staf mencatat mutasi barang harian atau memindai foto nota belanja.
                Mesin OCR lokal mengekstraksi teks draf transaksi untuk ditinjau
                secara berdampingan dengan foto sebelum resmi dibukukan.
              </p>
            </article>

            <article className="landing-card">
              <span className="landing-step-num">Langkah 2</span>
              <h3>Opname Fisik Berkala</h3>
              <p>
                Lakukan cek fisik terarah pada produk yang berisiko tinggi tanpa perlu
                menutup operasional toko. Input hitungan fisik langsung disandingkan
                dengan saldo sistem secara real-time.
              </p>
            </article>

            <article className="landing-card">
              <span className="landing-step-num">Langkah 3</span>
              <h3>Investigasi & Persetujuan</h3>
              <p>
                Jika ada selisih, sistem membuka kasus investigasi dengan batas waktu
                dan audit trail lengkap. Pemilik usaha meninjau alasan staf dan memutuskan
                apakah selisih disetujui atau wajib hitung ulang.
              </p>
            </article>
          </div>
        </section>

        {/* Keunggulan Integritas */}
        <section id="fitur" className="landing-section" aria-label="Keunggulan sistem">
          <h2>Keunggulan integritas data StokGuard</h2>
          <p className="muted">
            Fondasi arsitektur yang dirancang untuk mencegah kebocoran stok dan kecurangan data.
          </p>

          <div className="landing-grid">
            <article className="landing-card">
              <h3>Buku Besar Append-Only</h3>
              <p>
                Riwayat transaksi tidak dapat diedit atau dihapus diam-diam.
                Setiap koreksi kesalahan wajib melalui alur pengajuan pembalikan
                (reversal) resmi yang ditinjau pemilik.
              </p>
            </article>

            <article className="landing-card">
              <h3>Pemrosesan OCR Lokal Mandiri</h3>
              <p>
                Tesseract OCR berjalan langsung di server lokal Anda. Berkas foto nota
                dan data transaksi keuangan tersimpan privat di tempat usaha tanpa
                ketergantungan API cloud pihak ketiga.
              </p>
            </article>

            <article className="landing-card">
              <h3>Prioritas Risiko Deterministik</h3>
              <p>
                Sistem menghitung prioritas cek fisik produk menggunakan aturan
                deterministik 30 hari berdasarkan frekuensi selisih dan mutasi tanpa bukti,
                bukan skor perkiraan buatan.
              </p>
            </article>
          </div>
        </section>

        {/* Perbandingan Sebelum vs Sesudah */}
        <section id="perbandingan" className="landing-section" aria-label="Perbandingan sistem">
          <h2>Mengapa UMKM membutuhkan StokGuard?</h2>
          <p className="muted">
            Membandingkan cara pencatatan konvensional dengan sistem berbasis rekonsiliasi.
          </p>

          <div className="landing-compare-grid">
            <div className="landing-compare-card">
              <h3>Pencatatan Konvensional / Spreadsheet</h3>
              <ul>
                <li>Nota kertas mudah hilang, pudar, atau tercecer tanpa arsip digital terverifikasi.</li>
                <li>Angka saldo bisa diubah atau dihapus tanpa jejak siapa yang bertanggung jawab.</li>
                <li>Selisih barang baru disadari saat persediaan fisik habis di gudang.</li>
                <li>Tidak ada pemisahan wewenang antara pencatat mutasi dan penentu keputusan.</li>
              </ul>
            </div>

            <div className="landing-compare-card positive">
              <h3>Dengan StokGuard</h3>
              <ul>
                <li>Foto bukti nota terarsip digital dengan sidik jari SHA-256 dan deteksi duplikasi.</li>
                <li>Setiap mutasi terkunci permanen dalam log audit yang mencatat pengguna dan waktu.</li>
                <li>Selisih hitung fisik otomatis membuka tiket investigasi yang wajib dituntaskan.</li>
                <li>Pemisahan peran tegas antara staf operasional dan pemilik usaha.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Banner CTA */}
        <section className="landing-cta-banner" aria-label="Mulai sekarang">
          <h2>Mulai amankan stok usaha Anda</h2>
          <p className="muted">
            Akses sistem rekonsiliasi stok untuk memastikan pencatatan barang akurat dan transparan.
          </p>
          <Link href="/login" className="button">
            Masuk ke Aplikasi
          </Link>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div>
            <div className="wordmark">
              Stok<span>Guard</span>
            </div>
            <p className="muted" style={{ margin: "4px 0 0", fontSize: "14px" }}>
              Sistem rekonsiliasi dan investigasi selisih stok UMKM Indonesia.
            </p>
          </div>
          <div>
            <Link href="/login" className="button secondary">
              Halaman Masuk
            </Link>
          </div>
        </div>
      </footer>
    </>
  );
}
