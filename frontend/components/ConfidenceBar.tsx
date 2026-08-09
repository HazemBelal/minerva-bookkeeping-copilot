import type { Confidence } from "@/lib/types";

const LEVEL: Record<Confidence, number> = { low: 1, medium: 2, high: 3 };
const COLOR: Record<Confidence, string> = {
  low: "bg-amber-400",
  medium: "bg-sky-400",
  high: "bg-emerald-500",
};

export function ConfidenceBar({ value }: { value: Confidence | null }) {
  if (!value) return <span className="text-slate-300">—</span>;
  const filled = LEVEL[value];
  return (
    <span className="inline-flex items-center gap-1" title={`${value} confidence`}>
      {[1, 2, 3].map((i) => (
        <span
          key={i}
          className={`h-1.5 w-3 rounded-sm ${i <= filled ? COLOR[value] : "bg-slate-200"}`}
        />
      ))}
      <span className="ml-1 text-xs capitalize text-slate-500">{value}</span>
    </span>
  );
}
