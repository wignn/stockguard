# Panduan Deployment Produksi StokGuard (Docker & Bun)

Dokumen ini menjelaskan langkah-langkah deployment aplikasi **StokGuard** ke lingkungan produksi menggunakan **Docker Compose**, **Bun terbaru** untuk frontend Next.js 16 standalone, dan **Python 3.12 dengan Tesseract OCR** untuk backend API serta worker pemrosesan nota.

---

## 1. Arsitektur Layanan

```
                        [ Browser / Client ]
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │     Frontend (web)    │ (Port 3000)
                     │ Bun Latest Standalone │
                     └───────────┬───────────┘
                                 │ (Internal proxy rewrites /api/*)
                                 ▼
                     ┌───────────────────────┐
                     │      Backend (api)    │ (Port 8000)
                     │   FastAPI + Uvicorn   │
                     └───────────┬───────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
                 ▼                               ▼
    ┌─────────────────────────┐     ┌─────────────────────────┐
    │       Worker (worker)   │     │   Volume (stokguard_data)│
    │  Tesseract OCR (ID+EN)  │     │  - stokguard.db (WAL)   │
    │   Pemrosesan Bukti Nota │     │  - evidence/ (Berkas)   │
    └─────────────────────────┘     └─────────────────────────┘
```

- **Frontend (`web`)**:
  - Image: `oven/bun:latest` (Multi-stage build).
  - Framework: Next.js 16 App Router dengan `output: "standalone"`.
  - Berkas server minimal dan dependensi terisolasi dijalankan langsung oleh Bun runtime.
  - Melakukan reverse proxy internal untuk rute `/api/:path*` ke service backend `http://api:8000`.
- **Backend API (`api`)**:
  - Image: `python:3.12-slim-bookworm` dengan `uv` package manager.
  - Server: Uvicorn ASGI production server dengan proxy headers.
  - Auto-Migration: Menjalankan `alembic upgrade head` secara otomatis pada setiap boot container.
- **Worker OCR (`worker`)**:
  - Menjalankan antrean pemrosesan nota fisik di latar belakang (`python -m stokguard.cli worker`).
  - Dilengkapi binary Tesseract OCR dan data bahasa `ind` (Indonesia) serta `eng` (Inggris).
- **Persistent Storage (`stokguard_data`)**:
  - Docker named volume yang dipasang ke `/app/data`.
  - Menyimpan database SQLite (`stokguard.db`) dengan mode WAL (Write-Ahead Logging) dan direktori bukti nota fisik (`evidence/`).

---

## 2. Persyaratan Sistem

- Docker Engine 24.0+ atau Docker Desktop
- Docker Compose v2 (CLI plugin: `docker compose`)
- Minimum RAM 1.5 GB (direkomendasikan 2 GB+ untuk kompilasi Next.js dan OCR)
- Kapasitas disk yang memadai untuk penyimpanan bukti foto nota

---

## 3. Konfigurasi Lingkungan (`.env`)

Salin template konfigurasi dari `.env.example`:

```bash
cp .env.example .env
```

Contoh konfigurasi `.env` untuk produksi:

```ini
# Port binding
WEB_PORT=3000
API_PORT=8000

# Keamanan Cookie: Ubah ke true jika aplikasi diakses melalui HTTPS (domain publik)
STOKGUARD_SECURE_COOKIES=false

# Setup Otomatis (Opsional - isi jika ingin akun pemilik dibuat otomatis saat boot pertama)
AUTO_SETUP=false
BUSINESS_NAME="Toko Berkah Mandiri"
ADMIN_USERNAME="pemilik"
ADMIN_PASSWORD="PasswordMinimal12Karakter!"

# Demo Seeding (Opsional - isi jika ingin membuat data simulasi transaksi lengkap)
SEED_DEMO=false
DEMO_OWNER_USERNAME="demo-pemilik"
DEMO_STAFF_USERNAME="demo-staf"
DEMO_OWNER_PASSWORD="PasswordDemoPemilik123!"
DEMO_STAFF_PASSWORD="PasswordDemoStaf123!"
```

---

## 4. Langkah Build & Menjalankan

### Cara 1: Menggunakan Perintah Docker Compose Langsung

1. **Build image container:**
   ```bash
   docker compose build
   ```

2. **Jalankan seluruh service di latar belakang (detached mode):**
   ```bash
   docker compose up -d
   ```

3. **Periksa status kontainer dan healthcheck:**
   ```bash
   docker compose ps
   ```
   Pastikan service `stokguard-api`, `stokguard-web`, dan `stokguard-worker` berstatus `Up (healthy)`.

4. **Pantau log container:**
   ```bash
   docker compose logs -f
   ```

### Cara 2: Menggunakan Makefile

Jika server memiliki `make`:
```bash
make docker-build   # Build image
make docker-up      # Start stack
make docker-check   # Cek status kontainer
make docker-logs    # Pantau log
```

---

## 5. Inisialisasi Akun Pemilik Usaha

Jika tidak menggunakan opsi `AUTO_SETUP=true` di file `.env`, Anda dapat membuat akun pemilik pertama secara interaktif dengan prompt aman:

```bash
docker compose exec api python -m stokguard.cli setup --name "Nama Usaha Anda" --username "pemilik"
```
Container akan meminta input password dengan konfirmasi tanpa menampilkan teks di terminal.

Atau via Makefile:
```bash
make docker-setup BUSINESS_NAME="Nama Usaha Anda" USERNAME="pemilik"
```

---

## 6. Mengisi Data Percobaan (Demo Seed)

Untuk menguji fitur audit, deteksi selisih, dan transaksi dengan data lengkap:

```bash
docker compose exec api python -m stokguard.cli seed-demo
```
Atau via Makefile:
```bash
make docker-seed
```

---

## 7. Pemeliharaan & Operasi Lanjutan

### Menghentikan Layanan
```bash
docker compose down
```
*Catatan: Data di volume `stokguard_data` tetap aman dan tidak akan terhapus.*

### Backup Database & Bukti Nota
Untuk membuat arsip cadangan terkompresi dari database dan berkas bukti:
```bash
docker compose exec api python -m stokguard.cli backup --output /app/data/backup-$(date +%Y%m%d).tar.gz
```

### Mengaktifkan Mode Pemeliharaan (Maintenance Mode)
```bash
docker compose exec api python -m stokguard.cli maintenance on --reason "Pembaruan sistem"
```
Untuk mengembalikan status normal:
```bash
docker compose exec api python -m stokguard.cli maintenance off
```

---

## 8. Mengakses Aplikasi

Buka browser dan arahkan ke:
- **Aplikasi Web**: `http://<IP-SERVER>:3000`
- **Health Endpoint API**: `http://<IP-SERVER>:8000/health`
