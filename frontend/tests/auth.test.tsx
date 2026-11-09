import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { api, ApiError, setCsrfToken } from "@/lib/api";
import { AuthProvider, useAuth } from "@/lib/auth";
import { pendingMutations, prepareMutation } from "@/lib/idempotency";

it("uses cookies and CSRF without persisting auth tokens", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
  setCsrfToken("test-csrf");
  await api("/test", { method: "POST", body: { quantity: "2" } });
  const options = fetcher.mock.calls[0][1]!;
  expect(options.credentials).toBe("include");
  expect(new Headers(options.headers).get("X-CSRF-Token")).toBe("test-csrf");
  expect(localStorage.length).toBe(0);
});

it("returns structured conflicts without replacing the submitted input", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: { code: "stale_version", message: "Saldo berubah", request_id: "req-1", fields: null } }), { status: 409 }));
  const body = { quantity: "2", expected_balance_version: 1 };
  await expect(api("/movements", { method: "POST", body })).rejects.toMatchObject({ status: 409, code: "stale_version", requestId: "req-1" });
  expect(body).toEqual({ quantity: "2", expected_balance_version: 1 });
});

function AuthProbe() {
  const auth = useAuth();
  return <><span>{auth.session ? "signed in" : "signed out"}</span><button onClick={() => api("/private").catch(() => {})}>Expire</button><button onClick={() => void auth.logout()}>Logout</button><button onClick={() => void auth.login("owner", "password")}>Login</button></>;
}

it("clears the business query cache and auth on 401", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => String(input).endsWith("/auth/session")
    ? new Response(JSON.stringify({ user: { id: "user-1", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "business-1", name: "Toko", role: "owner" }] }), { status: 200 })
    : new Response(JSON.stringify({ error: { code: "invalid_session", message: "Masuk kembali" } }), { status: 401 }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["business", "private"], { sensitive: true });
  render(<QueryClientProvider client={client}><AuthProvider><AuthProbe /></AuthProvider></QueryClientProvider>);
  await screen.findByText("signed in");
  fireEvent.click(screen.getByRole("button", { name: "Expire" }));
  await waitFor(() => expect(screen.getByText("signed out")).toBeInTheDocument());
  expect(client.getQueryData(["business", "private"])).toBeUndefined();
  expect(ApiError).toBeDefined();
});

it("does not let the initial session lookup erase a successful login", async () => {
  let finish!: (response: Response) => void;
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => String(input).endsWith("/auth/session")
    ? new Promise((resolve) => { finish = resolve; })
    : Promise.resolve(new Response(JSON.stringify({ user: { id: "u", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "owner" }] }))));
  render(<QueryClientProvider client={new QueryClient()}><AuthProvider><AuthProbe /></AuthProvider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
  await screen.findByText("signed in");
  await act(async () => { finish(new Response(JSON.stringify({ error: { code: "invalid_session" } }), { status: 401 })); });
  expect(screen.getByText("signed in")).toBeInTheDocument();
});

it("ignores an aborted session response instead of clearing a newer login", async () => {
  let finish!: (response: Response) => void;
  vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  const expired = vi.fn();
  window.addEventListener("stokguard:unauthorized", expired);
  const controller = new AbortController();
  const request = api("/auth/session", { signal: controller.signal });
  controller.abort();
  finish(new Response(JSON.stringify({ error: { code: "invalid_session" } }), { status: 401 }));
  await expect(request).rejects.toThrow();
  expect(expired).not.toHaveBeenCalled();
  window.removeEventListener("stokguard:unauthorized", expired);
});

it("warns about uncertain mutations before logout and clears private browser state", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => new Response(JSON.stringify(String(input).endsWith("/auth/session") ? { user: { id: "u", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "owner" }] } : { status: "ok" }), { status: 200 }));
  const warning = vi.spyOn(window, "confirm").mockReturnValue(false);
  const client = new QueryClient();
  client.setQueryData(["private"], "secret");
  prepareMutation("b:movement", { quantity: "2" });
  render(<QueryClientProvider client={client}><AuthProvider><AuthProbe /></AuthProvider></QueryClientProvider>);
  await screen.findByText("signed in");
  fireEvent.click(screen.getByRole("button", { name: "Logout" }));
  expect(warning).toHaveBeenCalled();
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(pendingMutations()).toHaveLength(1);
  warning.mockReturnValue(true);
  fireEvent.click(screen.getByRole("button", { name: "Logout" }));
  await screen.findByText("signed out");
  expect(pendingMutations()).toHaveLength(0);
  expect(client.getQueryData(["private"])).toBeUndefined();
});
