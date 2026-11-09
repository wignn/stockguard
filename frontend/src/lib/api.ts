export const API_BASE = "/api/v1";
let csrfToken: string | null = null;
export function setCsrfToken(value: string | null): void { csrfToken = value; }

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string, public fields?: Record<string, string>) {
    super(message);
  }
}

export type ApiOptions = { method?: string; body?: unknown; idempotencyKey?: string; signal?: AbortSignal; timeoutMs?: number };

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers();
  const method = options.method || "GET";
  const body = options.body instanceof FormData ? options.body : options.body === undefined ? undefined : JSON.stringify(options.body);
  if (body && !(body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (method !== "GET" && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  if (options.idempotencyKey) headers.set("Idempotency-Key", options.idempotencyKey);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? 20_000);
  const abort = () => controller.abort();
  options.signal?.addEventListener("abort", abort, { once: true });
  if (options.signal?.aborted) controller.abort();
  try {
    const response = await fetch(`/api/v1${path}`, { method, body, headers, credentials: "include", signal: controller.signal, cache: "no-store" });
    const data = await response.json();
    if (controller.signal.aborted) throw new DOMException("Permintaan dibatalkan.", "AbortError");
    if (!response.ok) {
      if (response.status === 401) { setCsrfToken(null); window.dispatchEvent(new Event("stokguard:unauthorized")); }
      throw new ApiError(response.status, data.error?.code || "request_failed", data.error?.message || "Permintaan gagal. Coba lagi.", data.error?.request_id || response.headers.get("X-Request-ID") || undefined, data.error?.fields);
    }
    return data as T;
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abort);
  }
}
