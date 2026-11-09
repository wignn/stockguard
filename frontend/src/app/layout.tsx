import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = { title: { default: "StokGuard", template: "%s | StokGuard" }, description: "Pencatatan stok dan pemeriksaan selisih untuk usaha." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="id"><body><Providers>{children}</Providers></body></html>;
}
