import type { Row } from "./types";

const HEADERS = [
  "date", "description", "amount", "vendor", "category",
  "confidence", "source_url", "flags", "approved", "note",
];

function cell(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows: Row[]): string {
  const lines = [HEADERS.join(",")];
  for (const r of rows) {
    lines.push(
      [
        r.date, r.description, r.amount, r.merchant, r.category,
        r.confidence, r.source_url, r.flags.join(" | "),
        r.approved ? "yes" : "", r.note,
      ]
        .map(cell)
        .join(","),
    );
  }
  return lines.join("\n");
}

export function download(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
