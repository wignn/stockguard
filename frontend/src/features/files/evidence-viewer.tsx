"use client";
import { useState } from "react";
import { Dialog } from "@/components/dialog";
import { evidenceContentUrl, type EvidenceView } from "./api";
import { useAuth } from "@/lib/auth";
import { formatTime } from "@/lib/format";

export function EvidenceViewer({
  items,
  title = "Bukti terlampir",
}: {
  items: EvidenceView[];
  title?: string;
}) {
  const { business } = useAuth();
  const [selected, setSelected] = useState<EvidenceView | null>(null);

  if (!items.length || !business) return null;

  return (
    <div className="stack">
      <h3>{title}</h3>
      <ul className="file-list" aria-label={title}>
        {items.map((item) => (
          <li key={item.id}>
            <div>
              <strong>{item.original_name}</strong>
              <p className="hint">{item.width} × {item.height} piksel · {Math.max(1, Math.round(item.size_bytes / 1024))} KB<br />{formatTime(item.created_at)}</p>
              {item.duplicate_ids.length > 0 ? <span className="badge warning">Berkas identik ({item.duplicate_ids.length} berkas sama)</span> : <span className="hint">Tersimpan privat</span>}
            </div>
            <button type="button" className="secondary" aria-label={`Pratinjau bukti ${item.original_name}`} onClick={() => setSelected(item)}>Pratinjau bukti</button>
          </li>
        ))}
      </ul>

      {items.some((item) => item.duplicate_ids.length > 0) && (
        <div role="status" className="notice warning">
          <p>
            Peringatan duplikat: berkas dengan isi identik sudah pernah diunggah di usaha ini.
            Periksa kembali agar transaksi tidak dicatat dua kali; bukti tetap dapat digunakan
            untuk pemeriksaan kasus.
          </p>
        </div>
      )}

      <Dialog
        open={!!selected}
        title={selected ? `Pratinjau bukti · ${selected.original_name}` : "Pratinjau bukti"}
        onClose={() => setSelected(null)}
      >
        {selected && (
          <div className="stack">
            <p className="muted">
              Dimensi asli: {selected.width} × {selected.height} piksel · Format:{" "}
              {selected.mime_type}
            </p>
            <div className="evidence-frame">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={evidenceContentUrl(business.business_id, selected.id)}
                alt={`Bukti ${selected.original_name}`}
                width={selected.width}
                height={selected.height}
                style={{ maxWidth: "100%", height: "auto" }}
              />
            </div>
            <div className="actions">
              <a
                className="button secondary"
                href={evidenceContentUrl(business.business_id, selected.id)}
                download={selected.original_name}
              >
                Unduh berkas asli
              </a>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
