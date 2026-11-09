"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { FormField } from "@/components/form-field";
import { useAuth } from "@/lib/auth";

export function LoginForm() {
  const auth = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (auth.session) router.replace("/workspace"); }, [auth.session, router]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await auth.login(username, password); setPassword(""); router.replace("/workspace"); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Tidak dapat masuk. Coba lagi."); }
    finally { setBusy(false); }
  }
  return <div className="login-form"><h1>Masuk ke usaha Anda</h1><p className="muted">Gunakan akun yang disiapkan pemilik usaha.</p><form onSubmit={submit} aria-describedby={error ? "login-error" : undefined}>
    <FormField id="username" label="Nama pengguna"><input id="username" autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} aria-invalid={!!error} aria-describedby={error ? "login-error" : undefined} /></FormField>
    <FormField id="password" label="Password"><input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} aria-invalid={!!error} aria-describedby={error ? "login-error" : undefined} /></FormField>
    {error && <p id="login-error" className="notice error" role="alert">{error}</p>}
    <button type="submit" disabled={busy}>{busy ? "Memeriksa akun…" : "Masuk"}</button>
  </form><p className="hint" style={{ marginTop: 24 }}>Belum punya akun atau lupa password? Hubungi pemilik usaha. Pendaftaran mandiri belum tersedia.</p></div>;
}
