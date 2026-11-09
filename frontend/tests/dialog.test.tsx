import { readFileSync } from "node:fs";
import { render, screen, within } from "@testing-library/react";
import postcss from "postcss";
import { expect, it } from "vitest";
import { Dialog } from "@/components/dialog";

function installBaseStyles() {
  // jsdom cannot evaluate cascade layers or viewport layout. Apply the real
  // reset and unlayered base rules to check the modal's CSS contract only.
  const reset = postcss.parse(readFileSync("node_modules/tailwindcss/preflight.css", "utf8"));
  // jsdom rejects a whole selector list when it includes newer pseudo-elements.
  reset.walkRules((rule) => {
    if (rule.selectors.includes("*")) rule.selector = "*";
  });
  const app = postcss.parse(readFileSync("src/app/globals.css", "utf8"));
  const style = document.createElement("style");
  style.textContent = [reset, app].flatMap((root) => root.nodes
    .filter((node) => node.type === "rule")
    .map((node) => node.toString())).join("\n");
  document.head.append(style);
  return () => style.remove();
}

it("restores modal centering after the Tailwind reset and separates closing actions from the form", () => {
  const removeStyles = installBaseStyles();
  try {
    render(<Dialog open title="Tambah produk" onClose={() => {}}><form><label htmlFor="sku">Kode produk</label><input id="sku" /><button>Simpan produk</button></form></Dialog>);
    const dialog = screen.getByRole("dialog", { name: "Tambah produk" });
    const style = getComputedStyle(dialog);
    expect(style.marginTop).toBe("auto");
    expect(style.marginRight).toBe("auto");
    expect(style.marginBottom).toBe("auto");
    expect(style.marginLeft).toBe("auto");
    expect(style.position).toBe("fixed");
    expect(style.inset).toBe("0");
    expect(style.overflow).toBe("auto");
    const close = within(dialog).getByRole("button", { name: "Tutup" });
    expect(getComputedStyle(close.parentElement!).marginTop).toBe("20px");
    expect(close.closest("form")).toBeNull();
  } finally {
    removeStyles();
  }
});
