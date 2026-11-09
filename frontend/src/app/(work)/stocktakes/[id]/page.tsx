import { CountForm } from "@/features/stocktakes/count-form";

export default async function StocktakeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CountForm countId={id} />;
}
