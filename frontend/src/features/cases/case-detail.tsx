"use client";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Comparison } from "@/components/comparison";
import { FormField } from "@/components/form-field";
import { QueryState } from "@/components/query-state";
import { attachCaseEvidence } from "@/features/files/api";
import { EvidenceViewer } from "@/features/files/evidence-viewer";
import { EvidenceUploader } from "@/features/files/uploader";
import { movementNames } from "@/features/inventory/movement-form";
import { useStocktake, type Stocktake } from "@/features/stocktakes/api";
import { caseStatusNames, useCase, useCaseSubmissions, useProduct, useProductTimeline } from "./api";
import { DecisionPanel } from "./decision-panel";
import { causeNames, resolutionNames, SubmissionForm } from "./submission-form";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatQuantity, formatRupiah, formatTime } from "@/lib/format";

export { caseStatusNames };

export function CaseDetail({ caseId }: { caseId: string }) {
  const { business } = useAuth();
  const router = useRouter();
  const client = useQueryClient();
  const caseQuery = useCase(caseId);
  const caseItem = caseQuery.data;
  const product = useProduct(caseItem?.product_id);
  const latestCount = useStocktake(caseItem?.latest_stocktake_id || "");
  const submissions = useCaseSubmissions(caseId);
  const timeline = useProductTimeline(caseItem?.product_id, 0, 25);
  const [findingsDraft, setFindingsDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const currentFindings = findingsDraft ?? (caseItem?.findings || "");
  const currentSub = submissions.data?.items.find((item) => item.id === caseItem?.current_submission_id);
  const isStaleBalance = !!(product.data && latestCount.data && product.data.balance_version !== latestCount.data.baseline_version && caseItem?.status !== "resolved");

  async function saveFindings(event: FormEvent) {
    event.preventDefault();
    if (!business || !caseItem) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/businesses/${business.business_id}/cases/${caseItem.id}/findings`, {
        method: "PATCH",
        body: { expected_version: caseItem.version, note: currentFindings.trim() },
      });
      setFindingsDraft(null);
      setNotice("Temuan pemeriksaan tersimpan.");
      await client.invalidateQueries();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Temuan belum tersimpan.");
    } finally {
      setBusy(false);
    }
  }

  async function startRecount() {
    if (!business || !caseItem) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const created = await api<Stocktake>(`/businesses/${business.business_id}/stocktakes`, {
        method: "POST",
        body: { product_id: caseItem.product_id },
      });
      await client.invalidateQueries();
      router.push(`/stocktakes/${created.id}`);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Sesi hitung ulang belum dapat dimulai.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <QueryState
      loading={caseQuery.isPending || product.isPending || latestCount.isPending}
      error={caseQuery.error || product.error || latestCount.error}
      retry={() => { void caseQuery.refetch(); void product.refetch(); void latestCount.refetch(); }}
    >
      {caseItem && product.data && latestCount.data && (
        <div className="stack">
          <div className="page-heading">
            <div>
              <h1>Kasus selisih · {product.data.name}</h1>
              <p className="muted">
                Status: <strong>{caseStatusNames[caseItem.status] || caseItem.status}</strong> · Perkiraan nilai selisih: {formatRupiah(caseItem.estimated_value_rupiah)}
              </p>
            </div>
            {caseItem.status !== "resolved" && (
              <button type="button" className="secondary" disabled={busy} onClick={() => void startRecount()}>
                Mulai hitung ulang
              </button>
            )}
          </div>

          {error && <p role="alert" className="notice error">{error}</p>}
          {notice && <p role="status" className="notice">{notice}</p>}

          {(isStaleBalance || caseItem.status === "needs_recount") && (
            <div role="alert" className="notice warning">
              <p>Ada transaksi baru atau permintaan hitung ulang sejak opname terakhir. Lakukan hitung ulang fisik sebelum mengajukan atau menyetujui penyelesaian.</p>
            </div>
          )}

          <Comparison
            system={latestCount.data.baseline_quantity}
            physical={latestCount.data.counted_quantity || "0"}
            difference={caseItem.difference_quantity}
          />

          <div className="work-layout">
          <div className="work-column">
          <section className="panel stack" aria-label="Temuan pemeriksaan">
            <h2>Temuan pemeriksaan</h2>
            {caseItem.status === "resolved" ? (
              <p>{caseItem.findings || "Tidak ada catatan temuan tambahan."}</p>
            ) : (
              <form onSubmit={saveFindings} className="stack">
                <FormField id="case-findings" label="Catatan temuan pemeriksaan">
                  <textarea
                    id="case-findings"
                    required
                    value={currentFindings}
                    onChange={(event) => setFindingsDraft(event.target.value)}
                  />
                </FormField>
                <button type="submit" className="secondary" disabled={busy}>Simpan temuan</button>
              </form>
            )}
          </section>

          <section className="panel stack" aria-label="Bukti pemeriksaan kasus">
            <h2>Bukti foto pemeriksaan</h2>
            {(caseItem.evidence?.length || 0) > 0 ? (
              <EvidenceViewer items={caseItem.evidence || []} title="Bukti terlampir pada kasus ini" />
            ) : (
              <p className="muted">Belum ada berkas bukti yang dilampirkan pada kasus ini.</p>
            )}
            {caseItem.status !== "resolved" && business && (
              <EvidenceUploader
                label="Lampirkan foto bukti tambahan (JPG/PNG)"
                actionLabel="Unggah & lampirkan ke kasus"
                showList={false}
                onUploaded={async (item) => {
                  await attachCaseEvidence(business.business_id, caseItem.id, item.id);
                  await caseQuery.refetch();
                }}
              />
            )}
          </section>

          </div>
          <div className="work-column">
          {caseItem.status === "pending_review" && currentSub && (
            <DecisionPanel
              caseItem={caseItem}
              submission={currentSub}
              onDone={() => { void caseQuery.refetch(); void submissions.refetch(); }}
            />
          )}

          {(caseItem.status === "investigating" || caseItem.status === "rejected") && !isStaleBalance && (
            <SubmissionForm
              key={`${caseItem.version}-${caseItem.latest_stocktake_id}`}
              caseItem={caseItem}
              product={product.data}
              onDone={() => { void caseQuery.refetch(); void submissions.refetch(); }}
            />
          )}

          </div>
          </div>
          <details className="disclosure">
            <summary>Riwayat pengajuan</summary>
            {!submissions.data?.items.length ? (
              <p className="muted">Belum ada pengajuan pada kasus ini.</p>
            ) : (
              <div className="table-wrap responsive-table" tabIndex={0} role="region" aria-label="Gulir riwayat kasus">
                <table>
                  <caption className="sr-only">Riwayat pengajuan penyelesaian kasus</caption>
                  <thead>
                    <tr>
                      <th>Waktu</th>
                      <th>Penyebab</th>
                      <th>Tindak lanjut</th>
                      <th>Jumlah</th>
                      <th>Catatan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {submissions.data.items.map((sub) => (
                      <tr key={sub.id}>
                        <td data-label="Waktu">{formatTime(sub.submitted_at)}</td>
                        <td data-label="Penyebab">{causeNames[sub.cause] || sub.cause}</td>
                        <td data-label="Tindak lanjut">
                          {resolutionNames[sub.resolution_kind] || sub.resolution_kind}
                          {sub.movement_kind ? ` (${movementNames[sub.movement_kind] || sub.movement_kind})` : ""}
                        </td>
                        <td data-label="Jumlah">{formatQuantity(sub.quantity)} {product.data.unit}</td>
                        <td data-label="Catatan">{sub.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </details>

          <details className="disclosure">
            <summary>Transaksi terakhir produk ini</summary>
            {!timeline.data?.items.length ? (
              <p className="muted">Belum ada transaksi tercatat.</p>
            ) : (
              <div className="table-wrap responsive-table" tabIndex={0} role="region" aria-label="Gulir riwayat kasus">
                <table>
                  <caption className="sr-only">Linimasa transaksi produk</caption>
                  <thead>
                    <tr>
                      <th>Waktu</th>
                      <th>Jenis</th>
                      <th>Jumlah</th>
                      <th>Saldo sesudah</th>
                      <th>Catatan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeline.data.items.map((mov) => (
                      <tr key={mov.id}>
                        <td data-label="Waktu">{formatTime(mov.occurred_at)}</td>
                        <td data-label="Jenis">{movementNames[mov.kind] || mov.kind}</td>
                        <td data-label="Jumlah">{formatQuantity(mov.quantity)} {product.data.unit}</td>
                        <td data-label="Saldo sesudah">{formatQuantity(mov.balance_quantity)} {product.data.unit}</td>
                        <td data-label="Catatan">{mov.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </details>
        </div>
      )}
    </QueryState>
  );
}
