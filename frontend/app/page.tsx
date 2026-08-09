"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { GoalInput } from "@/components/GoalInput";
import { LedgerTable } from "@/components/LedgerTable";
import { RunControls } from "@/components/RunControls";
import { ScreenshotViewer } from "@/components/ScreenshotViewer";
import { useRunStream } from "@/lib/useRunStream";
import { toCsv, download } from "@/lib/csv";

const SAMPLE = `2026-07-02, SQSP* INV 8823941, -18.00
2026-07-03, AMZN MKTP US*2K4L9RT31, -42.19
2026-07-05, TST* GRAIN CAFE 4471, -63.40
2026-07-06, RAMP* CARD PAYMENT, -1250.00
2026-07-08, AMZN MKTP US, -42.19
2026-07-09, MERCURY BANK TRANSFER, 5000.00
2026-07-11, PADDLE.NET* FIGMA, -144.00
2026-07-12, UBER *EATS 8842, -31.75
2026-07-14, GUSTO PAYROLL FEE, -89.00
2026-07-15, SP CORDLESS DESK CO, -412.00`;

export default function Home() {
  const [goal, setGoal] = useState("Categorize these transactions.");
  const [statement, setStatement] = useState(SAMPLE);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [savedRunId, setSavedRunId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [approved, setApproved] = useState<Record<number, boolean>>({});
  const [overrides, setOverrides] = useState<Record<number, string>>({});

  const { state, reset } = useRunStream(streamUrl);

  useEffect(() => {
    fetch("/api/runs/latest")
      .then((r) => r.json())
      .then((d) => setSavedRunId(d.run_id))
      .catch(() => setSavedRunId(null));
  }, []);

  // Clears the viewer back to the input without a page reload. A reload would
  // re-trigger the cold-open replay in Task 10 and trap the user in it.
  const newRun = useCallback(() => {
    setStreamUrl(null);
    setRunId(null);
    setNotice(null);
    setApproved({});
    setOverrides({});
    reset();
  }, [reset]);

  const rows = useMemo(
    () =>
      state.rows.map((r) => ({
        ...r,
        approved: !!approved[r.id],
        overridden: overrides[r.id] !== undefined,
        category: overrides[r.id] ?? r.category,
      })),
    [state.rows, approved, overrides],
  );

  const start = useCallback(async () => {
    setNotice(null);
    setApproved({});
    setOverrides({});
    const res = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ goal, statement }),
    });
    if (!res.ok) {
      setNotice((await res.json().catch(() => ({}))).detail ?? "Could not start the run.");
      return;
    }
    const { run_id } = await res.json();
    setRunId(run_id);
    setStreamUrl(`/sse/runs/${run_id}`);
  }, [goal, statement]);

  const control = useCallback(
    (action: string) => {
      if (runId) fetch(`/api/runs/${runId}/${action}`, { method: "POST" });
    },
    [runId],
  );

  const busy = state.status === "running" || state.status === "paused";

  return (
    <main className="mx-auto max-w-[1400px] p-6">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Bookkeeping Copilot</h1>
          <p className="text-sm text-slate-500">
            Researches unknown merchants in a real browser, then categorizes them. Every
            answer carries a source you can check.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {savedRunId && (
            <button
              onClick={() => {
                newRun();
                setStreamUrl(`/sse/replay/${savedRunId}`);
              }}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              Replay a saved run
            </button>
          )}
          <RunControls
            status={state.status}
            onPause={() => control("pause")}
            onResume={() => control("resume")}
            onStop={() => control("stop")}
          />
        </div>
      </header>

      {notice && (
        <p className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {notice}
        </p>
      )}
      {state.error && (
        <p className="mb-4 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {state.error}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="space-y-4">
          {state.rows.length === 0 && (
            <GoalInput
              goal={goal}
              statement={statement}
              disabled={busy}
              onGoal={setGoal}
              onStatement={setStatement}
              onRun={start}
            />
          )}
          <LedgerTable
            rows={rows}
            onApprove={(id) => setApproved((a) => ({ ...a, [id]: !a[id] }))}
            onOverride={(id, category) => setOverrides((o) => ({ ...o, [id]: category }))}
          />
          {state.summary && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-sm text-slate-700">{state.summary}</p>
              <div className="flex gap-2">
                <button
                  onClick={() => download("ledger.csv", toCsv(rows))}
                  className="rounded border border-slate-300 px-3 py-1 text-sm"
                >
                  Export CSV
                </button>
                <button
                  onClick={newRun}
                  className="rounded border border-slate-300 px-3 py-1 text-sm"
                >
                  New run
                </button>
              </div>
            </div>
          )}
        </section>

        <aside className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            What the agent is doing
          </h2>
          <ActivityFeed items={state.activity} />
          <ScreenshotViewer url={state.screenshotUrl} label={state.screenshotLabel} />
        </aside>
      </div>
    </main>
  );
}
