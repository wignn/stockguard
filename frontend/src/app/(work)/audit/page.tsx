import { AuditList } from "@/features/audit/audit-list";

export default function AuditPage() {
  return (
    <div className="stack">
      <div>
        <h1>Log audit</h1>
        <p className="muted">
          Jejak seluruh perubahan stok, opname, kasus selisih, dan keputusan
          persetujuan pemilik secara kronologis.
        </p>
      </div>
      <AuditList />
    </div>
  );
}
