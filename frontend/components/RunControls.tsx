"use client";

import type { RunStatus } from "@/lib/types";

const LABEL: Record<RunStatus, string> = {
  idle: "Idle",
  running: "Running",
  paused: "Paused",
  stopped: "Stopped by you",
  done: "Complete",
  error: "Failed",
};

const DOT: Record<RunStatus, string> = {
  idle: "bg-slate-300",
  running: "bg-sky-500 animate-pulse",
  paused: "bg-amber-500",
  stopped: "bg-slate-500",
  done: "bg-emerald-500",
  error: "bg-red-500",
};

export function RunControls({
  status,
  onPause,
  onResume,
  onStop,
}: {
  status: RunStatus;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}) {
  const active = status === "running" || status === "paused";
  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex items-center gap-2 text-sm text-slate-600">
        <span className={`h-2 w-2 rounded-full ${DOT[status]}`} />
        {LABEL[status]}
      </span>
      {active && (
        <>
          <button
            onClick={status === "paused" ? onResume : onPause}
            className="rounded border border-slate-300 px-3 py-1 text-sm"
          >
            {status === "paused" ? "Resume" : "Pause"}
          </button>
          <button
            onClick={onStop}
            className="rounded bg-red-600 px-3 py-1 text-sm font-medium text-white"
          >
            Stop
          </button>
        </>
      )}
    </div>
  );
}
