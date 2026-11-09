import { expect, it } from "vitest";
import { completeMutation, pendingMutations, prepareMutation } from "@/lib/idempotency";

it("retains the exact key and canonical payload across an uncertain timeout", () => {
  const first = prepareMutation("movement:business-a", { quantity: "9007199254740993", expected_balance_version: 3 });
  const retry = prepareMutation("movement:business-a", { expected_balance_version: 3, quantity: "9007199254740993" });
  expect(retry.id).toBe(first.id);
  expect(retry.payload).toEqual(first.payload);
  expect(pendingMutations()).toHaveLength(1);
  expect(() => prepareMutation("movement:business-a", { quantity: "1" })).toThrow();
  completeMutation(first.id);
  expect(pendingMutations()).toHaveLength(0);
});
