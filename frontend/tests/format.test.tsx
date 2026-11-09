import { describe, expect, it } from "vitest";
import { formatRupiah, formatQuantity } from "@/lib/format";

describe("exact inventory amounts", () => {
  it("keeps values larger than the JavaScript safe integer", () => {
    expect(formatRupiah("9007199254740993")).toContain("9.007.199.254.740.993");
    expect(formatQuantity("9007199254740.993")).toBe("9.007.199.254.740,993");
    expect(formatQuantity("-6.5")).toBe("-6,5");
  });
});
