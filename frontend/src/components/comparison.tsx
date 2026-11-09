import { formatQuantity } from "@/lib/format";

export function Comparison({ system, physical, difference }: { system: string; physical: string; difference: string }) {
  return <dl className="comparison"><div><dt>Tercatat di sistem</dt><dd>{formatQuantity(system)}</dd></div><div><dt>Hitungan fisik</dt><dd>{formatQuantity(physical)}</dd></div><div className="difference"><dt>Selisih jumlah</dt><dd>{formatQuantity(difference)}</dd></div></dl>;
}
