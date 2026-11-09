import { CaseDetail } from "@/features/cases/case-detail";

export default async function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CaseDetail caseId={id} />;
}
