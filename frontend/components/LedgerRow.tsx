"use client";

import { CATEGORIES, type Row } from "@/lib/types";
import { ConfidenceBar } from "./ConfidenceBar";
import { FlagBadge } from "./FlagBadge";

const STATUS_STYLE: Record<Row["status"], string> = {
  pending: "text-slate-400",
  researching: "text-sky-600",
  done: "text-slate-900",
  needs_review: "text-amber-700",
};

export function LedgerRow({
  row,
  onApprove,
  onOverride,
}: {
  row: Row;
  onApprove: (id: number) => void;
  onOverride: (id: number, category: string) => void;
}) {
  return (
    <tr
      className={`border-b border-slate-100 align-top ${
        row.status === "needs_review" ? "bg-amber-50/60" : ""
      } ${row.approved ? "bg-emerald-50/50" : ""}`}
    >
      <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">{row.date || "—"}</td>
      <td className="px-3 py-2 font-mono text-xs text-slate-700">{row.description}</td>
      <td className="whitespace-nowrap px-3 py-2 text-right text-xs tabular-nums">
        {row.amount.toFixed(2)}
      </td>
      <td className={`px-3 py-2 text-sm ${STATUS_STYLE[row.status]}`}>
        {row.status === "researching" ? (
          <span className="inline-flex items-center gap-2">
            <span className="h-2 w-2 animate-pulse rounded-full bg-sky-500" />
            researching…
          </span>
        ) : (
          row.merchant ?? <span className="text-slate-300">—</span>
        )}
      </td>
      <td className="px-3 py-2 text-sm">
        {row.status === "pending" || row.status === "researching" ? (
          <span className="inline-block h-4 w-28 animate-pulse rounded bg-slate-100" />
        ) : (
          <select
            value={row.category ?? "Uncategorized"}
            onChange={(e) => onOverride(row.id, e.target.value)}
            className={`w-full rounded border px-1 py-0.5 text-sm ${
              row.overridden ? "border-sky-400 bg-sky-50" : "border-slate-200"
            }`}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
      </td>
      <td className="px-3 py-2">
        <ConfidenceBar value={row.confidence} />
      </td>
      <td className="px-3 py-2 text-xs">
        {row.source_url ? (
          <a
            href={row.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-sky-700 underline decoration-dotted"
          >
            source
          </a>
        ) : row.source === "model" ? (
          <span className="text-slate-400" title="Recognised without browsing">
            known
          </span>
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap gap-1">
          {row.flags.map((f) => (
            <FlagBadge key={f} code={f} />
          ))}
        </div>
        {row.note && <p className="mt-1 text-[11px] text-amber-700">{row.note}</p>}
      </td>
      <td className="px-3 py-2">
        <button
          onClick={() => onApprove(row.id)}
          disabled={row.status === "pending" || row.status === "researching"}
          className={`rounded px-2 py-1 text-xs ${
            row.approved
              ? "bg-emerald-600 text-white"
              : "border border-slate-300 text-slate-600 disabled:opacity-30"
          }`}
        >
          {row.approved ? "approved" : "approve"}
        </button>
      </td>
    </tr>
  );
}
