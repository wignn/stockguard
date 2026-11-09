export function formatRupiah(value: string): string {
  return `Rp${BigInt(value).toLocaleString("id-ID")}`;
}

export function formatQuantity(value: string): string {
  const [integer, fraction] = value.split(".");
  return `${BigInt(integer).toLocaleString("id-ID")}${fraction ? `,${fraction}` : ""}`;
}

export function formatTime(value: string): string {
  return new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
