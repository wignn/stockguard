"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Dialog } from "@/components/dialog";
import { useAuth } from "@/lib/auth";

const groups = [
  { label: "Pencatatan stok", links: [
    { href: "/dashboard", label: "Beranda" },
    { href: "/products", label: "Produk" },
    { href: "/record", label: "Catat transaksi" },
    { href: "/movements", label: "Riwayat transaksi" },
  ] },
  { label: "Pemeriksaan", links: [
    { href: "/stocktakes", label: "Opname" },
    { href: "/cases", label: "Kasus selisih" },
    { href: "/review", label: "Tinjauan pemilik" },
    { href: "/audit", label: "Log audit" },
  ] },
  { label: "Ruang usaha", links: [{ href: "/workspace", label: "Usaha saya" }] },
];
const mobileLinks = [
  { href: "/dashboard", label: "Beranda" },
  { href: "/record", label: "Catat" },
  { href: "/stocktakes", label: "Opname" },
  { href: "/cases", label: "Kasus" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [error, setError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => { if (!auth.loading && !auth.session && !auth.error) router.replace("/login"); }, [auth.loading, auth.session, auth.error, router]);

  function isActive(href: string) {
    return pathname === href || pathname.startsWith(`${href}/`) ||
      (href === "/record" && pathname.startsWith("/receipts/"));
  }
  const visibleGroups = groups.map((group) => ({
    ...group,
    links: group.links.filter((link) => link.href !== "/review" || auth.role === "owner"),
  }));
  const secondaryActive = !mobileLinks.some((link) => isActive(link.href));
  const logout = () => auth.logout().catch((failure) => setError(failure.message));

  if (auth.loading) return <main className="content"><p role="status">Memuat sesi…</p></main>;
  if (auth.error) return <main className="content"><div role="alert" className="notice error"><p>{auth.error}</p><button onClick={() => void auth.reload()}>Coba lagi</button></div></main>;
  if (!auth.session) return null;

  return <>
    <a className="skip" href="#main-content">Lewati navigasi</a>
    <div className="shell">
      <aside className="sidebar">
        <Link href="/dashboard" className="wordmark">Stok<span>Guard</span></Link>
        <p className="sidebar-intro">Catatan stok usaha Anda</p>
        <nav aria-label="Navigasi utama">
          {visibleGroups.map((group) => <div className="nav-group" key={group.label}>
            <p className="nav-group-label">{group.label}</p>
            {group.links.map((link) => <Link key={link.href} href={link.href} aria-current={isActive(link.href) ? "page" : undefined}>{link.label}</Link>)}
          </div>)}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="business-context">
            <Link href="/dashboard" className="wordmark mobile-wordmark">Stok<span>Guard</span></Link>
            {auth.session.memberships.length > 1 ? <>
              <label htmlFor="business-select">Usaha aktif</label>
              <select id="business-select" value={auth.business?.business_id || ""} onChange={(event) => auth.selectBusiness(event.target.value)}>
                {auth.session.memberships.map((membership) => <option key={membership.business_id} value={membership.business_id}>{membership.name}</option>)}
              </select>
            </> : <strong>{auth.business?.name || "Belum ada akses usaha"}</strong>}
            {auth.business?.is_demo && <span className="demo-label">Data demonstrasi</span>}
          </div>
          <div className="account">
            <span>{auth.session.user.username}<br /><small className="muted">{auth.role === "owner" ? "Pemilik" : "Staf"}</small></span>
            <button className="secondary" onClick={() => void logout()}>Keluar</button>
          </div>
        </header>
        <main id="main-content" className="content">{error && <p role="alert" className="notice error">{error}</p>}{children}</main>
      </div>
    </div>
    <nav className="mobile-nav" aria-label="Navigasi mobile">
      {mobileLinks.map((link) => <Link key={link.href} href={link.href} aria-current={isActive(link.href) ? "page" : undefined} onClick={() => setMenuOpen(false)}>{link.label}</Link>)}
      <button className={secondaryActive ? "menu-current" : ""} aria-expanded={menuOpen} aria-current={secondaryActive ? "true" : undefined} aria-haspopup="dialog" onClick={() => setMenuOpen(true)}>Menu</button>
    </nav>
    <Dialog open={menuOpen} title="Menu StokGuard" onClose={() => setMenuOpen(false)} footer={<button type="button" className="secondary" onClick={() => { setMenuOpen(false); void logout(); }}>Keluar dari akun</button>}>
      <div className="menu-account"><strong>{auth.session.user.username}</strong><span className="muted">{auth.role === "owner" ? "Pemilik" : "Staf"} di {auth.business?.name || "usaha Anda"}</span></div>
      <nav className="menu-links" aria-label="Navigasi tambahan">
        {visibleGroups.flatMap((group) => group.links).filter((link) => !mobileLinks.some((primary) => primary.href === link.href)).map((link) => <Link key={link.href} href={link.href} aria-current={isActive(link.href) ? "page" : undefined} onClick={() => setMenuOpen(false)}>{link.label}</Link>)}
      </nav>
    </Dialog>
  </>;
}
