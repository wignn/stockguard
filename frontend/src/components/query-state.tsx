import type { ReactNode } from "react";

export function QueryState({ loading, error, empty, retry, children }: { loading?: boolean; error?: unknown; empty?: string; retry?: () => void; children: ReactNode }) {
  if (loading) return <p role="status" className="muted">Memuat data…</p>;
  if (error) return <div className="notice error" role="alert"><p>{error instanceof Error ? error.message : "Data belum dapat dimuat."}</p>{retry && <button className="secondary" onClick={retry}>Muat ulang</button>}</div>;
  if (empty) return <div className="panel"><p>{empty}</p></div>;
  return children;
}
