import { readFileSync } from "node:fs";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import postcss from "postcss";
import { expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { CaseDetail } from "@/features/cases/case-detail";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

it("keeps investigation and submission in adjacent work areas and history collapsed", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    let data: unknown = {};
    if (url.endsWith("/auth/session")) data = { user: { id: "owner", username: "owner" }, csrf_token: "csrf", memberships: [{ business_id: "b", name: "Toko", role: "owner" }] };
    else if (url.includes("/submissions")) data = { items: [], total: 0 };
    else if (url.includes("/timeline")) data = { items: [], total: 0 };
    else if (url.includes("/stocktakes/")) data = { id: "st1", baseline_quantity: "10", counted_quantity: "8", baseline_version: 1 };
    else if (url.includes("/products/")) data = { id: "p1", name: "Sosis", unit: "Pcs", step_quantity: "1", balance_version: 1 };
    else if (url.includes("/cases/")) data = { id: "c1", product_id: "p1", latest_stocktake_id: "st1", status: "investigating", version: 1, difference_quantity: "-2", estimated_value_rupiah: "10000", evidence: [] };
    return new Response(JSON.stringify(data));
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthProvider><CaseDetail caseId="c1" /></AuthProvider></QueryClientProvider>);
  const findings = await screen.findByRole("region", { name: "Temuan pemeriksaan" });
  const submission = screen.getByRole("button", { name: "Kirim pengajuan ke pemilik" });
  expect(findings.closest(".work-layout")).not.toBeNull();
  expect(submission.closest(".work-layout")).toBe(findings.closest(".work-layout"));
  expect(submission.closest(".work-column")).not.toBe(findings.closest(".work-column"));
  const history = screen.getByText("Riwayat pengajuan", { selector: "summary" });
  expect(history.closest("details")).not.toHaveAttribute("open");
  fireEvent.click(history);
  expect(history.closest("details")).toHaveAttribute("open");
});

it("uses compact non-stretched form spacing after the real Tailwind reset", () => {
  const reset = postcss.parse(readFileSync("node_modules/tailwindcss/preflight.css", "utf8"));
  reset.walkRules(rule => { if (rule.selectors.includes("*")) rule.selector = "*"; });
  const app = postcss.parse(readFileSync("src/app/globals.css", "utf8"));
  const style = document.createElement("style");
  style.textContent = [reset, app].flatMap(root => root.nodes.filter(node => node.type === "rule").map(node => node.toString())).join("\n");
  document.head.append(style);
  try {
    render(<form className="stack"><div className="field"><label htmlFor="test-input">Jumlah</label><input id="test-input" /></div><button>Simpan</button></form>);
    expect(getComputedStyle(screen.getByRole("button", { name: "Simpan" })).justifySelf).toBe("start");
    expect(getComputedStyle(screen.getByLabelText("Jumlah").parentElement!).marginBottom).toBe("0px");
  } finally { style.remove(); }
});

it("defines a mobile stack and a desktop work grid without fixed content heights", () => {
  const app = postcss.parse(readFileSync("src/app/globals.css", "utf8"));
  const base: Record<string, string> = {};
  const desktop: Record<string, string> = {};
  app.walkRules(rule => {
    if (rule.selectors.includes(".work-layout")) rule.walkDecls(decl => {
      if (rule.parent?.type === "root") base[decl.prop] = decl.value;
      else if (rule.parent?.type === "atrule" && rule.parent.params.includes("1280px")) desktop[decl.prop] = decl.value;
    });
  });
  expect(base["grid-template-columns"]).toBe("minmax(0,1fr)");
  expect(desktop["grid-template-columns"]).toBe("repeat(2,minmax(0,1fr))");
  expect(base.height).toBeUndefined();
  expect(base.overflow).toBeUndefined();
});
