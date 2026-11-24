#!/bin/sh
set -e

# Pastikan folder penyimpanan data dan bukti fisik tersedia
mkdir -p /app/data/evidence

# Jalankan migrasi alembic hanya jika container dijalankan sebagai API server
case "$1" in
  uvicorn*)
    echo "[StokGuard] Memeriksa status dan menjalankan migrasi database..."
    python -m alembic upgrade head

    # Jalankan setup otomatis jika variabel lingkungan diaktifkan
    if [ "$AUTO_SETUP" = "true" ] && [ -n "$BUSINESS_NAME" ] && [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
        echo "[StokGuard] Menjalankan setup akun pemilik awal..."
        python -m stokguard.cli setup --name "$BUSINESS_NAME" --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" || true
    fi

    # Jalankan seed data demo otomatis jika variabel lingkungan diaktifkan
    if [ "$SEED_DEMO" = "true" ] && [ -n "$DEMO_OWNER_PASSWORD" ] && [ -n "$DEMO_STAFF_PASSWORD" ]; then
        echo "[StokGuard] Menjalankan seeding data demo..."
        python -m stokguard.cli seed-demo \
          --owner-username "${DEMO_OWNER_USERNAME:-demo-pemilik}" \
          --staff-username "${DEMO_STAFF_USERNAME:-demo-staf}" \
          --owner-password "$DEMO_OWNER_PASSWORD" \
          --staff-password "$DEMO_STAFF_PASSWORD" || true
    fi
    ;;
esac

# Jalankan perintah container utama
exec "$@"
