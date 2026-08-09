"use client";

import { useEffect, useRef } from "react";
import type { ActivityItem } from "@/lib/types";

const KIND_STYLE = {
  reasoning: "text-slate-700",
  action: "text-sky-700",
  error: "text-red-600",
} as const;

export function ActivityFeed({ items }: { items: ActivityItem[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [items.length]);

  return (
    <div className="h-64 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3">
      {items.length === 0 ? (
        <p className="text-xs text-slate-400">The agent has not started yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item) => (
            <li key={item.seq} className={`text-xs leading-snug ${KIND_STYLE[item.kind]}`}>
              {item.kind === "action" && <span className="mr-1 font-semibold">▸</span>}
              {item.text}
            </li>
          ))}
        </ul>
      )}
      <div ref={end} />
    </div>
  );
}
