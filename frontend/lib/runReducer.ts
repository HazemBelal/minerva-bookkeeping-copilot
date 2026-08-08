import type { ActivityItem, RunEvent, RunState, Row } from "./types";

const ACTIVITY_CAP = 300;

export function initialRunState(): RunState {
  return {
    runId: null,
    status: "idle",
    rows: [],
    activity: [],
    screenshotUrl: null,
    screenshotLabel: null,
    error: null,
    lastSeq: 0,
    summary: null,
  };
}

function pushActivity(state: RunState, item: ActivityItem): ActivityItem[] {
  const next = [...state.activity, item];
  return next.length > ACTIVITY_CAP ? next.slice(next.length - ACTIVITY_CAP) : next;
}

export function runReducer(state: RunState, event: RunEvent): RunState {
  const base = { ...state, runId: event.run_id, lastSeq: Math.max(state.lastSeq, event.seq) };
  const p = event.payload;

  switch (event.type) {
    case "plan": {
      const rows: Row[] = (p.rows ?? []).map((r: any) => ({
        id: r.id,
        date: r.date,
        description: r.description,
        amount: r.amount,
        merchant_key: r.merchant_key,
        merchant: null,
        category: null,
        confidence: null,
        source_url: null,
        reasoning: null,
        source: null,
        status: "pending",
        note: null,
        flags: [],
        approved: false,
        overridden: false,
      }));
      return { ...base, rows, status: "running" };
    }

    case "row_status": {
      const rows = base.rows.map((row) =>
        row.merchant_key === p.merchant_key
          ? {
              ...row,
              status: p.status ?? row.status,
              merchant: p.merchant ?? row.merchant,
              category: p.category ?? row.category,
              confidence: p.confidence ?? row.confidence,
              source_url: p.source_url ?? row.source_url,
              source: p.source ?? row.source,
              reasoning: p.reasoning ?? row.reasoning,
              note: p.note ?? row.note,
            }
          : row,
      );
      return { ...base, rows };
    }

    case "flag": {
      const ids: number[] = p.row_ids ?? [];
      const rows = base.rows.map((row) =>
        ids.includes(row.id) && !row.flags.includes(p.code)
          ? { ...row, flags: [...row.flags, p.code] }
          : row,
      );
      return { ...base, rows };
    }

    case "reasoning":
    case "action": {
      return {
        ...base,
        activity: pushActivity(base, {
          seq: event.seq,
          ts: event.ts,
          kind: event.type,
          merchant_key: p.merchant_key ?? null,
          text: p.text ?? p.name ?? "",
        }),
      };
    }

    case "screenshot": {
      return { ...base, screenshotUrl: p.url, screenshotLabel: p.label ?? null };
    }

    case "error": {
      const activity = pushActivity(base, {
        seq: event.seq,
        ts: event.ts,
        kind: "error",
        merchant_key: p.merchant_key ?? null,
        text: p.message ?? "Unknown error",
      });
      return p.fatal
        ? { ...base, activity, status: "error", error: p.message ?? "Unknown error" }
        : { ...base, activity };
    }

    case "done": {
      return {
        ...base,
        status: p.state === "stopped" ? "stopped" : "done",
        summary: p.summary ?? null,
      };
    }

    default:
      return base;
  }
}
