"use client";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FormField } from "@/components/form-field";
import type { CaseView, SubmissionView } from "./api";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { completeMutation, pendingMutations, prepareMutation, type PendingMutation } from "@/lib/idempotency";

export function DecisionPanel({ caseItem, submission, onDone }: { caseItem: CaseView; submission: SubmissionView; onDone: () => void }) {
  const { business, session, role } = useAuth();
  const client = useQueryClient();
  const scope = `decision:${business?.business_id}:${caseItem.id}`;
  const [pending, setPending] = useState<PendingMutation | undefined>(() =>
    typeof window === "undefined" ? undefined : pendingMutations().find((item) => item.scope === scope)
  );
  const [decision, setDecision] = useState<"approve" | "reject" | "recount">("approve");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (role !== "owner") return null;

  const isSelf = submission.user_id === session?.user.id;

  async function send(item: PendingMutation) {
    if (!business) return;
    setBusy(true); setError("");
    try {
      await api(`/businesses/${business.business_id}/cases/${caseItem.id}/decisions`, {
        method: "POST",
        body: item.payload,
        idempotencyKey: item.id,
      });
      completeMutation(item.id);
      setPending(undefined);
      await client.invalidateQueries();
      onDone();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status < 500) {
        completeMutation(item.id);
        setPending(undefined);
        if (failure.code === "recount_required") {
          await client.invalidateQueries();
          onDone();
        }
      } else {
        setPending(item);
      }
      setError(failure instanceof Error ? failure.message : "Keputusan belum tersimpan.");
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const item = prepareMutation(scope, {
        expected_case_version: caseItem.version,
        submission_id: submission.id,
        decision,
        note: note.trim(),
      });
      setPending(item);
      await send(item);
    } catch (failure) {
      setError((failure as Error).message);
    }
  }

  return (
    <section className="panel form-width stack" aria-label="Tinjauan usulan">
      <h2>Keputusan pemilik</h2>
      {isSelf && (
        <div role="alert" className="notice warning">
          <p>Anda mengajukan usulan ini sendiri. Pengaju tidak dapat menyetujui atau memutuskan pengajuannya sendiri. Minta pemilik lain meninjau, atau mintakan staf mengajukan ulang setelah pemeriksaan.</p>
        </div>
      )}
      {pending && (
        <div className="notice">
          <p>Keputusan sebelumnya belum mendapat kepastian jaringan.</p>
          <button type="button" disabled={busy} onClick={() => void send(pending)}>Ulangi keputusan asli</button>
        </div>
      )}
      {error && <p role="alert" className="notice error">{error}</p>}
      <form onSubmit={submit} className="stack">
        <fieldset disabled={busy || !!pending || isSelf}>
          <FormField id="case-decision" label="Keputusan pemilik">
            <select id="case-decision" value={decision} onChange={(event) => setDecision(event.target.value as "approve" | "reject" | "recount")}>
              <option value="approve">Setujui dan jalankan tindak lanjut</option>
              <option value="reject">Tolak pengajuan (kembalikan ke penelusuran)</option>
              <option value="recount">Minta hitung ulang fisik</option>
            </select>
          </FormField>
          <FormField id="case-decision-note" label="Catatan keputusan" hint={decision === "approve" ? "Opsional untuk persetujuan." : "Wajib diisi untuk penolakan atau permintaan hitung ulang."}>
            <textarea id="case-decision-note" required={decision !== "approve"} value={note} onChange={(event) => setNote(event.target.value)} />
          </FormField>
          <button type="submit" disabled={busy || isSelf}>{busy ? "Menyimpan…" : "Simpan keputusan kasus"}</button>
        </fieldset>
      </form>
    </section>
  );
}
