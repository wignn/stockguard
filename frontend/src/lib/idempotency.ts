export type PendingMutation = { id: string; scope: string; payload: unknown; canonical: string };
const STORAGE_KEY = "stokguard.pending";

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function pendingMutations(): PendingMutation[] {
  return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "[]");
}

export function prepareMutation(scope: string, payload: unknown): PendingMutation {
  const text = canonical(payload);
  const pending = pendingMutations();
  const existing = pending.find((item) => item.scope === scope);
  if (existing) {
    if (existing.canonical !== text) throw new Error("Hasil permintaan sebelumnya belum pasti. Periksa atau ulangi isian yang sama.");
    return existing;
  }
  const item = { id: crypto.randomUUID(), scope, payload: JSON.parse(text), canonical: text };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...pending, item]));
  return item;
}

export function completeMutation(id: string): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pendingMutations().filter((item) => item.id !== id)));
}

export function clearPendingMutations(): void { sessionStorage.removeItem(STORAGE_KEY); }
