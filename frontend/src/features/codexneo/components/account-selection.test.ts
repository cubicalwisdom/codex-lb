import { describe, expect, it } from "vitest";

import { applyAccountSelectionRange } from "./account-selection";

describe("applyAccountSelectionRange", () => {
  it("selects every visible account between the anchor and shift-clicked row", () => {
    const selected = applyAccountSelectionRange({
      current: ["acct-a"],
      visible: ["acct-a", "acct-b", "acct-c", "acct-d"],
      accountKey: "acct-c",
      checked: true,
      rangeSelect: true,
      anchorKey: "acct-a",
    });

    expect(selected).toEqual(["acct-a", "acct-b", "acct-c"]);
  });

  it("uses the existing selected row as a range anchor when the last clicked row is unavailable", () => {
    const selected = applyAccountSelectionRange({
      current: ["acct-a"],
      visible: ["acct-a", "acct-b", "acct-c"],
      accountKey: "acct-c",
      checked: true,
      rangeSelect: true,
      anchorKey: null,
    });

    expect(selected).toEqual(["acct-a", "acct-b", "acct-c"]);
  });
});
