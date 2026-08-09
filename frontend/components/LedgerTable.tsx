"use client";

import type { Row } from "@/lib/types";
import { LedgerRow } from "./LedgerRow";

const HEADERS = [
  "Date", "Description", "Amount", "Vendor", "Category",
  "Confidence", "Source", "Flags", "",
];

export function LedgerTable({
  rows,
  onApprove,
  onOverride,
}: {
  rows: Row[];
  onApprove: (id: number) => void;
  onOverride: (id: number, category: string) => void;
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 p-10 text-center text-sm text-slate-400">
        Paste a bank statement and press Run. Rows appear here as the agent works.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full border-collapse text-left">
        <thead className="bg-slate-50">
          <tr>
            {HEADERS.map((h) => (
              <th
                key={h}
                className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <LedgerRow key={row.id} row={row} onApprove={onApprove} onOverride={onOverride} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
