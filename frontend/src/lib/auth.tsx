"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, setCsrfToken } from "./api";
import { clearPendingMutations, pendingMutations } from "./idempotency";

export type Membership = { business_id: string; name: string; role: "owner" | "staff"; timezone: string; is_demo: boolean };
export type Session = { user: { id: string; username: string }; expires_at: string; csrf_token: string; memberships: Membership[] };
type Auth = { session: Session | null; business: Membership | null; role: "owner" | "staff" | null; loading: boolean; error: string; login: (username: string, password: string) => Promise<void>; logout: () => Promise<void>; selectBusiness: (id: string) => void; reload: () => Promise<void> };
const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const sessionLookup = useRef<AbortController | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [businessId, setBusinessId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const reset = useCallback(() => { setSession(null); setBusinessId(null); setCsrfToken(null); client.clear(); clearPendingMutations(); }, [client]);
  const accept = useCallback((value: Session) => { setSession(value); setCsrfToken(value.csrf_token); setBusinessId(value.memberships[0]?.business_id || null); setError(""); }, []);
  const reload = useCallback(async () => {
    sessionLookup.current?.abort();
    const controller = new AbortController();
    sessionLookup.current = controller;
    setLoading(true);
    try { accept(await api<Session>("/auth/session", { signal: controller.signal })); }
    catch (failure) { if (!controller.signal.aborted) { if (failure instanceof ApiError && failure.status === 401) reset(); else setError("Sesi belum dapat dimuat. Periksa koneksi lalu coba lagi."); } }
    finally { if (sessionLookup.current === controller) setLoading(false); }
  }, [accept, reset]);
  useEffect(() => {
    const controller = new AbortController();
    sessionLookup.current = controller;
    window.addEventListener("stokguard:unauthorized", reset);
    api<Session>("/auth/session", { signal: controller.signal }).then(accept).catch((failure) => {
      if (!controller.signal.aborted && !(failure instanceof ApiError && failure.status === 401)) setError("Sesi belum dapat dimuat. Periksa koneksi lalu coba lagi.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { controller.abort(); window.removeEventListener("stokguard:unauthorized", reset); };
  }, [accept, reset]);
  const login = async (username: string, password: string) => { sessionLookup.current?.abort(); setLoading(false); accept(await api<Session>("/auth/login", { method: "POST", body: { username, password, mode: "web" } })); };
  const logout = async () => {
    if (pendingMutations().length && !window.confirm("Ada permintaan yang hasilnya belum pasti. Keluar akan menghapus salinan permintaan di browser. Periksa riwayat setelah masuk kembali. Tetap keluar?")) return;
    await api("/auth/logout", { method: "POST" }); reset();
  };
  const business = session?.memberships.find((item) => item.business_id === businessId) || null;
  return <AuthContext.Provider value={{ session, business, role: business?.role || null, loading, error, login, logout, reload, selectBusiness: (id) => { client.clear(); setBusinessId(id); } }}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth { const value = useContext(AuthContext); if (!value) throw new Error("AuthProvider diperlukan"); return value; }
