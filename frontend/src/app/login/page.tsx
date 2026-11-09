import type { Metadata } from "next";
import { LoginForm } from "@/features/auth/login-form";
export const metadata: Metadata = { title: "Masuk" };
export default function LoginPage() {
  return <main className="login-page"><section className="login-aside" aria-label="StokGuard"><div className="wordmark">Stok<span>Guard</span></div><div><h2>Catat stok.<br />Periksa selisihnya.</h2><p style={{ marginTop: 24 }}>Sandingkan catatan transaksi dengan hitungan fisik, lalu telusuri perbedaannya bersama pemilik usaha.</p></div><p className="muted">Selisih adalah awal pemeriksaan, bukan kesimpulan.</p></section><section className="login-main" aria-label="Formulir masuk"><LoginForm /></section></main>;
}
