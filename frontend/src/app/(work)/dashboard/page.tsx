import { PriorityList } from "@/features/risk/priority-list";

export default function DashboardPage() {
  return (
    <div className="stack">
      <div>
        <h1>Dashboard prioritas stok</h1>
        <p className="muted">
          Daftar produk yang paling memerlukan pemeriksaan fisik berdasarkan riwayat
          selisih, pergerakan stok, dan usia opname terakhir.
        </p>
      </div>
      <PriorityList />
    </div>
  );
}
