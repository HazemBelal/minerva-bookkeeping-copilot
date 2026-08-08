"use client";

import { useEffect, useReducer, useState } from "react";
import { initialRunState, runReducer } from "./runReducer";
import type { RunEvent, RunState } from "./types";

export function useRunStream(url: string | null): {
  state: RunState;
  connected: boolean;
  reset: () => void;
} {
  const [state, dispatch] = useReducer(
    (s: RunState, e: RunEvent | "reset") =>
      e === "reset" ? initialRunState() : runReducer(s, e),
    undefined,
    initialRunState,
  );
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!url) return;
    const source = new EventSource(url);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (m) => {
      try {
        dispatch(JSON.parse(m.data) as RunEvent);
      } catch {
        // A malformed frame must not kill the stream.
      }
    };
    return () => source.close();
  }, [url]);

  return { state, connected, reset: () => dispatch("reset") };
}
