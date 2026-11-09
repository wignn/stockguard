"use client";
import { useState } from "react";
import { FormField } from "@/components/form-field";
import { QueryState } from "@/components/query-state";
import { auditCsvExportUrl, useAuditEvents } from "./api";
import { useAuth } from "@/lib/auth";
import { formatTime } from "@/lib/format";

function toStartIso(dateStr: string): string {
  if (!dateStr) return "";
  return `${dateStr}T00:00:00Z`;
}

function toEndExclusiveIso(dateStr: string): string {
  if (!dateStr) return "";
  const base = new Date(`${dateStr}T00:00:00Z`);
  base.setUTCDate(base.getUTCDate() + 1);
  return base.toISOString();
}

export function AuditList() {
  const { business } = useAuth();
  const [offset, setOffset] = useState(0);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const limit = 25;

  const fromIso = toStartIso(fromDate);
  const toIso = toEndExclusiveIso(toDate);
  const events = useAuditEvents(offset, limit, fromIso, toIso);

  if (!business) return null;

  const exportHref = auditCsvExportUrl(business.business_id, fromIso, toIso);
  const total = events.data?.total || 0;

  return (
    <div className="stack">
      <section className="panel stack" aria-label="Filter dan ekspor log audit">
        <div className="page-heading">
          <div>
            <h2>Filter rentang waktu & ekspor CSV</h2>
            <p className="muted">
              Catatan audit bersifat hanya-baca (append-only) dan tidak memiliki
              tindakan sunting maupun penghapusan. Ekspor CSV otomatis menetralkan
              rumus spreadsheet berbahaya.
            </p>
          </div>
          <a
            className="button secondary"
            href={exportHref}
            download="stokguard-audit.csv"
          >
            Unduh CSV audit
          </a>
        </div>

        <div className="split">
          <FormField id="audit-from" label="Dari tanggal (UTC)">
            <input
              id="audit-from"
              type="date"
              value={fromDate}
              onChange={(event) => {
                setFromDate(event.target.value);
                setOffset(0);
              }}
            />
          </FormField>
          <FormField id="audit-to" label="Sampai tanggal (UTC)">
            <input
              id="audit-to"
              type="date"
              value={toDate}
              onChange={(event) => {
                setToDate(event.target.value);
                setOffset(0);
              }}
            />
          </FormField>
        </div>
      </section>

      <QueryState
        loading={events.isPending}
        error={events.error}
        retry={() => void events.refetch()}
      >
        <section className="panel stack" aria-label="Tabel jejak audit">
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Gulir tabel jejak audit">
            <table>
              <caption className="sr-only">Jejak audit append-only</caption>
              <thead>
                <tr>
                  <th>Waktu</th>
                  <th>Tindakan</th>
                  <th>Entitas</th>
                  <th>Pelaku (ID pengguna)</th>
                  <th>Ringkasan perubahan</th>
                </tr>
              </thead>
              <tbody>
                {(events.data?.items || []).map((item) => (
                  <tr key={item.id}>
                    <td>{formatTime(item.occurred_at)}</td>
                    <td>
                      <code>{item.action}</code>
                    </td>
                    <td>
                      {item.entity_type} · <code>{item.entity_id.slice(0, 8)}</code>
                    </td>
                    <td>{item.user_id ? <code>{item.user_id.slice(0, 8)}</code> : "Sistem"}</td>
                    <td>
                      <code className="audit-json">
                        {JSON.stringify(item.changes)}
                      </code>
                    </td>
                  </tr>
                ))}
                {events.data?.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">
                      Tidak ada catatan audit pada rentang waktu yang dipilih.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="actions">
            <button
              type="button"
              className="secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              Sebelumnya
            </button>
            <span>{total} catatan audit</span>
            <button
              type="button"
              className="secondary"
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
            >
              Berikutnya
            </button>
          </div>
        </section>
      </QueryState>
    </div>
  );
}
