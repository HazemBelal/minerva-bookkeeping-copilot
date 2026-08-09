import { FLAG_LABELS } from "@/lib/types";

export function FlagBadge({ code }: { code: string }) {
  return (
    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-800">
      {FLAG_LABELS[code] ?? code}
    </span>
  );
}
