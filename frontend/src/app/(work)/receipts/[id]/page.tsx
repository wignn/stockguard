import { DraftEditor } from "@/features/receipts/draft-editor";

export default async function ReceiptDraftPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <DraftEditor draftId={id} />;
}
