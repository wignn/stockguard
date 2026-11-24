import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "StokGuard - Rekonsiliasi & Audit Stok Fisik UMKM",
  description:
    "Sistem rekonsiliasi stok fisik dan pembukuan append-only untuk UMKM. Sandingkan transaksi harian dengan hitungan fisik di rak, verifikasi nota belanja via OCR lokal, dan audit selisih secara transparan.",
};

export default function HomePage() {
  return (
    <>
      <header className="landing-nav" role="banner">
        <Link href="/" className="wordmark" aria-label="Beranda StokGuard">
          Stok<span>Guard</span>
        </Link>
        <nav className="landing-nav-links" aria-label="Navigasi umum">
          <a href="#alur">Alur Operasional</a>
          <a href="#perbandingan">Masalah Lapangan</a>
          <a href="#peran">Pembagian Peran</a>
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
          <div className="badge">Pencatatan Stok Lokal & Anti-Manipulasi UMKM</div>
          <h1>Saat toko tutup sore ini, apa barang di rak benar-benar cocok dengan catatan kasir?</h1>
          <p>
            StokGuard dirancang untuk toko kelontong, distributor sembako, dan ritel UMKM yang lelah
            dengan selisih barang di akhir bulan. Mengunci mutasi stok dalam buku besar yang tidak bisa
            diedit diam-diam, membaca nota belanja kertas lewat OCR lokal, dan membuka investigasi
            resmi tiap kali ada selisih fisik.
          </p>
          <div className="actions">
            <Link href="/login" className="button">
              Masuk ke Usaha Anda
            </Link>
            <a href="#alur" className="button secondary">
              Pelajari Alur Kerja
            </a>
          </div>
        </section>

        {/* Real Operational Workflows with Concrete UI Previews */}
        <section id="alur" className="landing-section" aria-label="Alur kerja operasional">
          <h2>Tiga alur kerja nyata di lantai toko</h2>
          <p className="muted">
            Bukan teori manajemen yang rumit. Tiga langkah konkret yang bisa langsung dijalankan
            staf gudang dan pemilik toko setiap hari.
          </p>

          <div className="preview-showcase">
            {/* Workflow 1: Opname Fisik & Tiket Selisih */}
            <article className="preview-item">
              <div className="preview-card" aria-label="Simulasi antarmuka opname fisik">
                <div className="preview-bar">
                  <span>Sesi Opname Fisik #ST-019 · Rak Depan</span>
                  <span className="badge warning">Perlu Investigasi</span>
                </div>
                <div className="preview-content">
                  <div>
                    <strong>Minyak Goreng Sawit 2L Pouch</strong>
                    <div className="muted" style={{ fontSize: "13px" }}>SKU: MNY-02 · Satuan Pouch</div>
                  </div>
                  <div className="comparison">
                    <div>
                      <dt>Saldo Sistem</dt>
                      <dd>48</dd>
                    </div>
                    <div>
                      <dt>Hitungan Fisik</dt>
                      <dd>44</dd>
                    </div>
                    <div className="difference">
                      <dt>Selisih Fisik</dt>
                      <dd style={{ color: "var(--danger)" }}>-4 Pouch</dd>
                    </div>
                  </div>
                  <div className="notice warning" style={{ margin: 0, fontSize: "13px" }}>
                    <strong>Kasus Selisih #CASE-104 dibuka otomatis (Tenggat 24 Jam)</strong>
                    <div style={{ marginTop: "4px" }}>
                      Catatan staf: <em>&quot;2 pouch bocor di kardus bawah, 2 pouch tester display belum tercatat.&quot;</em> Menunggu keputusan pemilik.
                    </div>
                  </div>
                </div>
              </div>
              <div className="preview-note">
                <h3>1. Opname fisik terarah tanpa tutup toko</h3>
                <p>
                  Staf tidak perlu menghitung ratusan jenis barang sekaligus. Sistem memprioritaskan
                  produk yang paling rawan selisih atau yang sering bergerak tanpa nota bukti dalam
                  30 hari terakhir. Jika hitungan di rak berbeda dengan saldo sistem, tiket investigasi
                  langsung terbuka otomatis.
                </p>
              </div>
            </article>

            {/* Workflow 2: OCR Nota Belanja Pasar */}
            <article className="preview-item">
              <div className="preview-card" aria-label="Simulasi ekstraksi nota OCR">
                <div className="preview-bar">
                  <span>Draf Nota Masuk #REC-202611 · Toko Grosir Sumber Rejeki</span>
                  <span className="badge risk-low">OCR Selesai</span>
                </div>
                <div className="preview-content">
                  <div style={{ display: "grid", gap: "8px", background: "#f4f6f9", padding: "12px", borderRadius: "8px", border: "1px dashed var(--line)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
                      <strong>Bukti Foto Nota #7719</strong>
                      <span className="muted">Tercap LUNAS · 24 Nov</span>
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--muted)", fontStyle: "italic" }}>
                      Foto nota kertas diproses langsung di mesin Tesseract lokal server toko.
                    </div>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Item Terbaca</th>
                          <th>Kuantitas</th>
                          <th style={{ textAlign: "right" }}>Subtotal</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Gula Pasir Kristal 1kg</td>
                          <td>20 Pcs</td>
                          <td style={{ textAlign: "right" }}>Rp 330.000</td>
                        </tr>
                        <tr>
                          <td>Susu Kental Manis 370g</td>
                          <td>24 Klg</td>
                          <td style={{ textAlign: "right" }}>Rp 276.000</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                    <span className="button secondary" style={{ fontSize: "13px", minHeight: "36px", padding: "6px 12px" }}>Koreksi Baris</span>
                    <span className="button" style={{ fontSize: "13px", minHeight: "36px", padding: "6px 12px" }}>Setujui & Tambah Stok</span>
                  </div>
                </div>
              </div>
              <div className="preview-note">
                <h3>2. Nota pasar basah atau supplier langsung dipindai</h3>
                <p>
                  Nota belanja sering kusut, basah, atau tercecer di laci. Staf cukup memotret
                  nota lewat kamera HP. Mesin OCR lokal mengekstrak nomor nota, tanggal, nama barang,
                  dan total belanja. Hasilnya disandingkan berdampingan dengan foto asli untuk
                  diverifikasi manusia sebelum resmi dibukukan.
                </p>
              </div>
            </article>

            {/* Workflow 3: Append-Only Ledger */}
            <article className="preview-item">
              <div className="preview-card" aria-label="Simulasi mutasi buku besar append-only">
                <div className="preview-bar">
                  <span>Buku Besar Mutasi Stok · Kopi Robusta 250g</span>
                  <span className="badge">Terkunci Permanen</span>
                </div>
                <div className="preview-content">
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Waktu</th>
                          <th>Jenis Mutasi</th>
                          <th>Jumlah</th>
                          <th>Saldo Akhir</th>
                          <th>Oleh</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>08:30</td>
                          <td>Barang Masuk</td>
                          <td style={{ color: "var(--success)" }}>+20 Pcs</td>
                          <td>45 Pcs</td>
                          <td>staf_gudang</td>
                        </tr>
                        <tr>
                          <td>13:15</td>
                          <td>Penjualan Kasir</td>
                          <td style={{ color: "var(--danger)" }}>-5 Pcs</td>
                          <td>40 Pcs</td>
                          <td>kasir_1</td>
                        </tr>
                        <tr>
                          <td>16:45</td>
                          <td>Pembalikan Koreksi</td>
                          <td style={{ color: "var(--warning)" }}>-2 Pcs</td>
                          <td><strong>38 Pcs</strong></td>
                          <td>pemilik</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="notice" style={{ margin: 0, fontSize: "13px", background: "#fdf8ee", borderColor: "#f3d99e" }}>
                    <strong>Tidak ada tombol &quot;Hapus Mutasi&quot;</strong>
                    <div style={{ marginTop: "4px" }}>
                      Semua transaksi tercatat permanen. Koreksi salah input harus melalui pengajuan pembalikan resmi dengan jejak audit dua pihak.
                    </div>
                  </div>
                </div>
              </div>
              <div className="preview-note">
                <h3>3. Tidak ada riwayat transaksi yang bisa diedit diam-diam</h3>
                <p>
                  Di spreadsheet biasa, angka di baris mana pun bisa diganti tanpa jejak. Di StokGuard,
                  buku besar bersifat append-only. Sekali mutasi tercatat, catatan tersebut tidak bisa
                  diubah atau dihapus. Jika ada kesalahan input, staf mengajukan pembatalan (reversal)
                  yang wajib disetujui pemilik toko.
                </p>
              </div>
            </article>
          </div>
        </section>

        {/* Realita Masalah Lapangan */}
        <section id="perbandingan" className="landing-section" aria-label="Masalah operasional toko">
          <h2>Realita lapangan: Mengapa cara lama selalu bocor?</h2>
          <p className="muted">
            Tiga celah terbesar pembukuan manual dan spreadsheet yang diselesaikan oleh StokGuard.
          </p>

          <div className="landing-compare-grid">
            <div className="landing-compare-card">
              <h3>Celah 1: File Excel Bisa Diedit Diam-diam</h3>
              <p className="muted" style={{ fontSize: "14px", lineHeight: "1.6" }}>
                Saat barang di gudang berkurang, sangat mudah bagi oknum untuk mengganti angka saldo di cell Excel tanpa ada catatan siapa yang mengubahnya.
              </p>
              <div style={{ marginTop: "12px", borderTop: "1px solid var(--line)", paddingTop: "12px", fontSize: "14px", color: "var(--ink)", fontWeight: "500" }}>
                Di StokGuard: Saldo dihitung murni dari rantai mutasi terkunci. Setiap transaksi punya catatan pengguna dan waktu mutlak.
              </div>
            </div>

            <div className="landing-compare-card">
              <h3>Celah 2: Kertas Bon Luntur & Tercecer</h3>
              <p className="muted" style={{ fontSize: "14px", lineHeight: "1.6" }}>
                Nota thermal cepat pudar, nota pasar basah terkena minyak sayur, dan kertas bon belanja sering hilang di saku staf sebelum sempat direkap.
              </p>
              <div style={{ marginTop: "12px", borderTop: "1px solid var(--line)", paddingTop: "12px", fontSize: "14px", color: "var(--ink)", fontWeight: "500" }}>
                Di StokGuard: Staf cukup memotret nota lewat HP. Berkas tersimpan lokal dengan sidik jari SHA-256 untuk mendeteksi nota ganda.
              </div>
            </div>

            <div className="landing-compare-card">
              <h3>Celah 3: Opname Cuma Pas Akhir Bulan</h3>
              <p className="muted" style={{ fontSize: "14px", lineHeight: "1.6" }}>
                Menghitung selisih hanya sebulan sekali membuat barang yang hilang tiga minggu lalu mustahil dilacak penyebab dan siapa yang bertugas saat itu.
              </p>
              <div style={{ marginTop: "12px", borderTop: "1px solid var(--line)", paddingTop: "12px", fontSize: "14px", color: "var(--ink)", fontWeight: "500" }}>
                Di StokGuard: Opname harian terarah per 1-2 rak dalam hitungan 5 menit. Selisih langsung ditindaklanjuti sebelum bukti terlupakan.
              </div>
            </div>
          </div>
        </section>

        {/* Roles Breakdown */}
        <section id="peran" className="landing-section" aria-label="Pemisahan peran wewenang">
          <h2>Pembagian wewenang yang tegas antara pemilik dan staf</h2>
          <p className="muted">
            Mencegah konflik internal dengan alur kerja yang transparan dan dapat dipertanggungjawabkan.
          </p>

          <div className="split" style={{ marginTop: "24px" }}>
            <div className="panel stack">
              <h3>Pemilik Usaha (Owner)</h3>
              <ul style={{ margin: 0, paddingLeft: "20px", display: "grid", gap: "8px", fontSize: "15px", color: "var(--ink)" }}>
                <li>Melihat produk prioritas yang paling sering mengalami selisih dalam 30 hari.</li>
                <li>Menyetujui atau menolak penyelesaian tiket kasus selisih opname fisik.</li>
                <li>Mengesahkan permohonan pembalikan (reversal) transaksi yang keliru.</li>
                <li>Mengendalikan harga pokok barang dan menambahkan akun staf baru.</li>
              </ul>
            </div>

            <div className="panel stack">
              <h3>Staf Toko & Gudang (Staff)</h3>
              <ul style={{ margin: 0, paddingLeft: "20px", display: "grid", gap: "8px", fontSize: "15px", color: "var(--ink)" }}>
                <li>Mencatat mutasi barang masuk dan keluar saat transaksi berlangsung.</li>
                <li>Memotret nota belanja dan memeriksa draf hasil pembacaan OCR lokal.</li>
                <li>Menghitung fisik barang di rak saat jadwal opname tanpa melihat saldo acuan sistem.</li>
                <li>Memberikan keterangan tertulis jika terdapat barang rusak atau hilang.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Banner CTA */}
        <section className="landing-cta-banner" aria-label="Mulai sekarang">
          <h2>Mulai amankan stok fisik toko Anda</h2>
          <p className="muted">
            Gunakan sistem rekonsiliasi yang transparan, aman, dan siap dijalankan langsung di tempat usaha Anda.
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
