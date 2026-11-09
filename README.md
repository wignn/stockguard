# StokGuard

Aplikasi lokal untuk pencatatan stok barang jadi UMKM, opname fisik, investigasi selisih, dan persetujuan pemilik. Antarmuka berbahasa Indonesia. Backend Python terpisah dari frontend agar API dapat dipakai klien lain nanti.

## Komponen

- `backend/`: FastAPI, SQLAlchemy, SQLite WAL, Alembic, worker OCR lokal.
- `frontend/`: Next.js App Router, React, TypeScript, TanStack Query.
- `docs/`: spesifikasi, rencana implementasi, kontrak API, dan panduan operasi.
- `data/`: database dan bukti privat lokal, tidak masuk Git.

Mutasi stok memakai ledger append-only. Koreksi dilakukan melalui alur persetujuan atau pembalikan, bukan mengedit riwayat. Kuantitas API berupa string desimal maksimal tiga angka di belakang koma; biaya berupa string rupiah bulat. Hasil OCR selalu berupa draf yang harus ditinjau manusia sebelum dibukukan.

## Jalankan dengan Makefile

Dari direktori proyek (GNU Make, `uv`, dan npm harus tersedia):

```powershell
make install
make setup BUSINESS_NAME="Nama usaha" USERNAME=pemilik
make run
```

`make setup` hanya untuk membuat usaha/akun baru; password diminta melalui prompt tersembunyi. Untuk menjalankan lagi setelah setup, cukup `make run`.

Buka `http://127.0.0.1:3000`. `make run` menjalankan API port 8000, frontend port 3000, dan worker OCR secara paralel di terminal yang sama. Tekan Ctrl+C untuk menghentikan proses. Tidak menjalankan Playwright, membuat akun bawaan, atau memasang Tesseract.

Bila ingin terminal terpisah, gunakan `make backend`, `make frontend`, dan `make worker`. Perintah lain: `make help`, `make build`, dan `make check` (lint/typecheck saja, tanpa tes browser).

### Data demo

Untuk mencoba data contoh, gunakan `make seed` sebagai alternatif `make setup`:

```powershell
make seed
make run
```

Seed membuat usaha berlabel demo, produk, stok awal, transaksi, dan kasus selisih. Akun default bernama `demo-pemilik` dan `demo-staf`; password keduanya diminta melalui prompt tersembunyi, tidak ada password bawaan. Nama akun dapat diganti: `make seed DEMO_OWNER=pemilik-contoh DEMO_STAFF=staf-contoh`. Jangan jalankan seed berulang dengan nama akun yang sama.

Disarankan memakai direktori terpisah dari data usaha nyata. Di PowerShell, set sebelum **seed dan run**:

```powershell
$env:STOKGUARD_DATA_DIR = Join-Path $PWD "data-demo"
make seed
make run
```

Port dapat diganti, misalnya `make run API_PORT=8002`. Frontend otomatis memakai `API_ORIGIN` sesuai port API. Jika mengganti `WEB_PORT`, sesuaikan allowlist origin backend sesuai [panduan operasi](docs/local-operations.md).

## Mulai di Windows (PowerShell) tanpa Make

Prasyarat: Python 3.12+, `uv`, Node.js 20.9+ dan npm. Tesseract opsional untuk OCR, bukan syarat pencatatan manual. Tidak ada akun/password produksi bawaan.

Dari direktori proyek:

```powershell
uv sync --project backend --locked
npm --prefix frontend ci
uv run --project backend python -m stokguard.cli setup --name "Nama usaha" --username pemilik
```

Masukkan password melalui prompt tersembunyi. Simpan UUID usaha yang dicetak, lalu buat akun staf dengan UUID tersebut:

```powershell
uv run --project backend python -m stokguard.cli add-user UUID_USAHA staf --role staff
```

Jalankan masing-masing di terminal terpisah dari direktori proyek:

```powershell
uv run --project backend uvicorn stokguard.main:create_app --factory --host 127.0.0.1 --port 8000
```

```powershell
uv run --project backend python -m stokguard.cli worker
```

```powershell
npm --prefix frontend run dev
```

Buka `http://127.0.0.1:3000`. Frontend meneruskan `/api/` ke backend lokal. API docs tersedia di `http://127.0.0.1:8000/docs`.

Untuk data contoh, gunakan `seed-demo` secara sengaja, idealnya pada direktori data terpisah. Perintah meminta password pemilik dan staf, dan menandai usaha sebagai data demo. Lihat [panduan operasi lokal](docs/local-operations.md).

## Verifikasi

```powershell
uv run --project backend ruff check backend
uv run --project backend pytest backend/tests -q
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend run e2e -- --workers=1
```

E2E memakai backend/data sementara dan Chrome lokal. Tes OCR nyata dilewati bila Tesseract tidak tersedia; itu bukan bukti OCR nyata berhasil.

## Batas penggunaan

SQLite harus berada di disk lokal, bukan network share atau folder sinkronisasi. Aplikasi ini belum disiapkan sebagai layanan internet publik. Akses LAN membutuhkan konfigurasi HTTPS, origin, cookie, dan pembatasan jaringan yang benar. Backup berisi data sensitif dan harus disimpan dengan perlindungan akses/enkripsi yang sesuai.

Hasil dan batas verifikasi: [laporan verifikasi](docs/verification.md).

Panduan lengkap: [operasi lokal](docs/local-operations.md), [kontrak API](docs/api-contract.md), [spesifikasi](docs/superpowers/specs/2026-11-09-stokguard-design.md).

## Troubleshooting

- Seed melaporkan `Username sudah digunakan`: akun sudah ada di direktori data aktif. Masuk memakai akun/password lama, atau buat demo baru dengan **kedua** nama akun berbeda: `make seed DEMO_OWNER=pemilik-demo-2 DEMO_STAFF=staf-demo-2`. Untuk isolasi penuh, pilih `STOKGUARD_DATA_DIR` baru sebelum seed dan run. Seed tidak mereset password atau menghapus data lama.
- `503 maintenance_mode`: periksa `python -m stokguard.cli maintenance status` melalui `uv run --project backend`. Jangan matikan maintenance saat backup/cleanup masih berjalan.
- Login gagal: gunakan akun yang dibuat melalui CLI dan periksa origin frontend. Ubah password lewat `change-password USERNAME`; seluruh sesi akun dicabut.
- OCR tidak tersedia: jalankan `ocr-check`, lalu gunakan draf manual sampai Tesseract dikonfigurasi. Instalasi executable sistem memerlukan persetujuan operator.
- Konflik versi: muat ulang data dan periksa riwayat. Jangan mengirim ulang transaksi dengan kunci idempotensi baru sebelum memastikan hasil permintaan awal.
- E2E tidak menemukan Chrome: sediakan browser yang disetujui operator atau ubah konfigurasi channel secara sengaja. Tidak ada unduhan browser otomatis dalam aplikasi.
