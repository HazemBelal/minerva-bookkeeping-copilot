"use client";

import { useState } from "react";
import { useRunStream } from "@/lib/useRunStream";

export default function Home() {
  const [url, setUrl] = useState<string | null>(null);
  const { state, connected } = useRunStream(url);

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-semibold">Bookkeeping Copilot</h1>
      <button
        className="mt-4 rounded bg-slate-900 px-4 py-2 text-white"
        onClick={() => setUrl("/sse/demo")}
      >
        Connect to demo stream
      </button>
      <p className="mt-2 text-sm text-slate-500">
        {connected ? "connected" : "not connected"} · {state.activity.length} events
      </p>
      <ul className="mt-4 space-y-1 font-mono text-xs">
        {state.activity.slice(-10).map((a) => (
          <li key={a.seq}>{a.text}</li>
        ))}
      </ul>
    </main>
  );
}
