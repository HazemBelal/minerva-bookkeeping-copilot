import { describe, it, expect } from "vitest";
import { initialRunState, runReducer } from "@/lib/runReducer";
import type { RunEvent } from "@/lib/types";

const ev = (seq: number, type: RunEvent["type"], payload: Record<string, unknown>): RunEvent => ({
  run_id: "r1",
  seq,
  ts: seq,
  type,
  payload,
});

const planEvent = ev(1, "plan", {
  rows: [
    { id: 0, date: "2026-07-02", description: "SQSP* INV", amount: -18, merchant_key: "sqsp" },
    { id: 1, date: "2026-07-03", description: "AMZN MKTP US*2K", amount: -42.19, merchant_key: "amzn" },
    { id: 2, date: "2026-07-08", description: "AMZN MKTP US", amount: -42.19, merchant_key: "amzn" },
  ],
  research_count: 1,
});

describe("runReducer", () => {
  it("creates pending rows from the plan event", () => {
    const s = runReducer(initialRunState(), planEvent);
    expect(s.rows).toHaveLength(3);
    expect(s.rows.every((r) => r.status === "pending")).toBe(true);
    expect(s.runId).toBe("r1");
  });

  it("applies a row_status to every row sharing the merchant key", () => {
    let s = runReducer(initialRunState(), planEvent);
    s = runReducer(
      s,
      ev(2, "row_status", {
        merchant_key: "amzn",
        status: "done",
        merchant: "Amazon",
        category: "Office Supplies",
        confidence: "high",
        source_url: "https://amazon.com",
        source: "model",
        reasoning: "Marketplace retail purchase",
      }),
    );
    expect(s.rows[1].merchant).toBe("Amazon");
    expect(s.rows[2].merchant).toBe("Amazon");
    expect(s.rows[0].merchant).toBeNull();
  });

  it("records needs_review with the reason instead of dropping the row", () => {
    let s = runReducer(initialRunState(), planEvent);
    s = runReducer(
      s,
      ev(2, "row_status", {
        merchant_key: "sqsp",
        status: "needs_review",
        note: "Hit the 6 step limit without a confident match",
      }),
    );
    expect(s.rows[0].status).toBe("needs_review");
    expect(s.rows[0].note).toMatch(/6 step limit/);
  });

  it("appends flags without clobbering existing ones", () => {
    let s = runReducer(initialRunState(), planEvent);
    s = runReducer(s, ev(2, "flag", { row_ids: [1, 2], code: "duplicate_charge" }));
    s = runReducer(s, ev(3, "flag", { row_ids: [2], code: "repeat_merchant" }));
    expect(s.rows[2].flags).toEqual(["duplicate_charge", "repeat_merchant"]);
    expect(s.rows[1].flags).toEqual(["duplicate_charge"]);
  });

  it("caps the activity feed and tracks lastSeq", () => {
    let s = runReducer(initialRunState(), planEvent);
    for (let i = 2; i < 350; i++) {
      s = runReducer(s, ev(i, "reasoning", { text: `step ${i}`, merchant_key: "amzn" }));
    }
    expect(s.activity.length).toBeLessThanOrEqual(300);
    expect(s.activity[s.activity.length - 1].text).toBe("step 349");
    expect(s.lastSeq).toBe(349);
  });

  it("marks done and stores the summary", () => {
    let s = runReducer(initialRunState(), planEvent);
    s = runReducer(s, ev(2, "done", { summary: "3 rows, 1 flag" }));
    expect(s.status).toBe("done");
    expect(s.summary).toBe("3 rows, 1 flag");
  });

  it("surfaces a fatal error rather than failing silently", () => {
    let s = runReducer(initialRunState(), planEvent);
    s = runReducer(s, ev(2, "error", { message: "OpenAI rate limit", fatal: true }));
    expect(s.status).toBe("error");
    expect(s.error).toBe("OpenAI rate limit");
  });

  it("stores a screenshot url and label", () => {
    let s = runReducer(initialRunState(), planEvent);
    s = runReducer(
      s,
      ev(2, "screenshot", { url: "/shots/r1/2.png", label: "Amazon receipt" }),
    );
    expect(s.screenshotUrl).toBe("/shots/r1/2.png");
    expect(s.screenshotLabel).toBe("Amazon receipt");
  });

  it("defaults a screenshot event missing url/label to null instead of undefined", () => {
    let s = runReducer(initialRunState(), planEvent);
    s = runReducer(s, ev(2, "screenshot", {}));
    expect(s.screenshotUrl).toBeNull();
    expect(s.screenshotLabel).toBeNull();
  });

  it("falls back to payload.name for action activity text when text is absent", () => {
    let s = runReducer(initialRunState(), planEvent);
    s = runReducer(
      s,
      ev(2, "action", { name: "click_search_button", merchant_key: "amzn" }),
    );
    const last = s.activity[s.activity.length - 1];
    expect(last.kind).toBe("action");
    expect(last.text).toBe("click_search_button");
    expect(last.merchant_key).toBe("amzn");
  });
});
