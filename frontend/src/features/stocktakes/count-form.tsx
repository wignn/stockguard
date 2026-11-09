"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Comparison } from "@/components/comparison";
import { FormField } from "@/components/form-field";
import { QueryState } from "@/components/query-state";
import { useStocktake } from "./api";
import { useProduct } from "@/features/cases/api";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatQuantity, formatTime } from "@/lib/format";

function toMilli(value: string): bigint | null {
  const trimmed = value.trim();
  if (!/^-?\d+(?:\.\d{1,3})?$/.test(trimmed)) return null;
  const neg = trimmed.startsWith("-");
  const clean = neg ? trimmed.slice(1) : trimmed;
  const [intPart, frac = ""] = clean.split(".");
  const milli = BigInt(intPart) * 1000n + BigInt(frac.padEnd(3, "0"));
  return neg ? -milli : milli;
}

function fromMilli(milli: bigint): string {
  const neg = milli < 0n;
  const abs = neg ? -milli : milli;
  const intPart = abs / 1000n;
  const fracPart = abs % 1000n;
  if (fracPart === 0n) return `${neg ? "-" : ""}${intPart}`;
  const fracStr = fracPart.toString().padStart(3, "0").replace(/0+$/, "");
  return `${neg ? "-" : ""}${intPart}.${fracStr}`;
}

export function CountForm({ countId }: { countId: string }) {
  const { business, session, role } = useAuth();
  const client = useQueryClient();
  const stocktake = useStocktake(countId);
  const count = stocktake.data;
  const product = useProduct(count?.product_id);
  const [counted, setCounted] = useState("");
  const [noPhysical, setNoPhysical] = useState(false);
  const [recounted, setRecounted] = useState(false);
  const [rackChecked, setRackChecked] = useState(false);
  const [storageChecked, setStorageChecked] = useState(false);
  const [cancelNote, setCancelNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const baseMilli = count ? toMilli(count.baseline_quantity) : null;
  const countedMilli = toMilli(counted);
  const diffMilli = baseMilli !== null && countedMilli !== null ? countedMilli - baseMilli : null;
  const hasDiff = diffMilli !== null && diffMilli !== 0n;
  const canSubmit = countedMilli !== null && countedMilli >= 0n && noPhysical && (!hasDiff || (recounted && rackChecked && storageChecked));

  async function finalize(event: FormEvent) {
    event.preventDefault();
    if (!business || !count || !canSubmit) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/businesses/${business.business_id}/stocktakes/${count.id}/finalize`, {
        method: "POST",
        body: {
          counted_quantity: counted.trim(),
          expected_version: count.version,
          no_physical_movement: noPhysical,
          recounted: hasDiff ? recounted : false,
          rack_checked: hasDiff ? rackChecked : false,
          storage_checked: hasDiff ? storageChecked : false,
        },
      });
      await client.invalidateQueries();
      await stocktake.refetch();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Opname belum dapat diselesaikan.");
    } finally {
      setBusy(false);
    }
  }

  async function act(action: "extend" | "cancel") {
    if (!business || !count) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/businesses/${business.business_id}/stocktakes/${count.id}/${action}`, {
        method: "POST",
        body: { expected_version: count.version, note: cancelNote },
      });
      setNotice(action === "extend" ? "Batas waktu sesi diperpanjang." : "Sesi opname dibatalkan.");
      await client.invalidateQueries();
      await stocktake.refetch();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Tindakan opname belum berhasil.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <QueryState loading={stocktake.isPending || product.isPending} error={stocktake.error || product.error} retry={() => { void stocktake.refetch(); void product.refetch(); }}>
      {count && product.data && (
        <div className="stack">
          <div className="page-heading">
            <div>
              <h1>Sesi opname · {product.data.name}</h1>
              <p className="muted">SKU {product.data.sku} · Satuan {product.data.unit} · Dimulai {formatTime(count.started_at)} · Batas sesi {formatTime(count.expires_at)}</p>
            </div>
            <Link className="button secondary" href="/stocktakes">Daftar opname</Link>
          </div>

          {error && <p role="alert" className="notice error">{error}</p>}
          {notice && <p role="status" className="notice">{notice}</p>}

          {count.status === "finalized" && (
            <div className="panel stack">
              <Comparison system={count.baseline_quantity} physical={count.counted_quantity || "0"} difference={count.difference_quantity || "0"} />
              {count.case_id ? (
                <div className="notice warning">
                  <p>Selisih fisik ditemukan ({formatQuantity(count.difference_quantity || "0")} {product.data.unit}). Selisih adalah awal pemeriksaan, bukan kesimpulan.</p>
                  <Link className="button" href={`/cases/${count.case_id}`}>Buka kasus investigasi</Link>
                </div>
              ) : (
                <p role="status" className="notice success">Jumlah fisik sesuai catatan sistem. Tidak ada kasus selisih dibuka.</p>
              )}
            </div>
          )}

          {count.status !== "active" && count.status !== "finalized" && (
            <div className="notice warning">
              <p>Status sesi ini: {count.status === "expired" ? "Kedaluwarsa" : "Dibatalkan"}. Mulai sesi opname baru bila pemeriksaan fisik masih diperlukan.</p>
              <Link className="button secondary" href="/stocktakes">Mulai sesi baru</Link>
            </div>
          )}

          {count.status === "active" && (
            <form onSubmit={finalize} className="stack">
              <div className="work-layout">
                <div className="work-column">
                  <section className="panel stack" aria-label="Input dan perbandingan fisik">
                    <h2>Hitungan fisik</h2>
                    <FormField id="counted-quantity" label="Jumlah fisik terhitung" hint={`Satuan ${product.data.unit}. Langkah ${product.data.step_quantity}.`}>
                      <input
                        id="counted-quantity"
                        type="number"
                        inputMode="decimal"
                        min="0"
                        step={product.data.step_quantity}
                        required
                        value={counted}
                        onChange={(event) => setCounted(event.target.value)}
                      />
                    </FormField>

                    <Comparison
                      system={count.baseline_quantity}
                      physical={countedMilli !== null ? fromMilli(countedMilli) : count.baseline_quantity}
                      difference={diffMilli !== null ? fromMilli(diffMilli) : "0"}
                    />
                  </section>
                </div>

                <div className="work-column">
                  <fieldset className="panel stack">
                    <legend><strong>Konfirmasi sebelum menyelesaikan opname</strong></legend>
                    <label className="check-label" htmlFor="chk-no-movement">
                      <input id="chk-no-movement" type="checkbox" checked={noPhysical} onChange={(event) => setNoPhysical(event.target.checked)} />
                      Tidak ada perpindahan barang fisik selama sesi hitung berlangsung
                    </label>

                    {hasDiff && (
                      <>
                        <p className="hint">Terdapat selisih sebanyak {fromMilli(diffMilli!)} {product.data.unit}. Lengkapi pemeriksaan fisik sebelum membuka atau memperbarui kasus:</p>
                        <label className="check-label" htmlFor="chk-recounted">
                          <input id="chk-recounted" type="checkbox" checked={recounted} onChange={(event) => setRecounted(event.target.checked)} />
                          Sudah dihitung ulang secara fisik
                        </label>
                        <label className="check-label" htmlFor="chk-rack">
                          <input id="chk-rack" type="checkbox" checked={rackChecked} onChange={(event) => setRackChecked(event.target.checked)} />
                          Area rak pajang sudah diperiksa
                        </label>
                        <label className="check-label" htmlFor="chk-storage">
                          <input id="chk-storage" type="checkbox" checked={storageChecked} onChange={(event) => setStorageChecked(event.target.checked)} />
                          Area penyimpanan/gudang sudah diperiksa
                        </label>
                      </>
                    )}

                    {role === "owner" && count.user_id !== session?.user.id && (
                      <FormField id="cancel-note" label="Alasan pembatalan pemilik">
                        <input id="cancel-note" value={cancelNote} onChange={(event) => setCancelNote(event.target.value)} />
                      </FormField>
                    )}

                    <div className="actions">
                      <button type="submit" disabled={!canSubmit || busy}>{busy ? "Menyimpan…" : "Selesaikan opname"}</button>
                      <button type="button" className="secondary" disabled={busy} onClick={() => void act("extend")}>Perpanjang 15 menit</button>
                      <button type="button" className="secondary" disabled={busy} onClick={() => void act("cancel")}>Batalkan sesi</button>
                    </div>
                  </fieldset>
                </div>
              </div>
            </form>
          )}
        </div>
      )}
    </QueryState>
  );
}
