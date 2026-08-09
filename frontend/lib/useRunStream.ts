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
        const event = JSON.parse(m.data) as RunEvent;
        dispatch(event);
        // The server always closes the stream right after a `done` event.
        // Left alone, the browser's native EventSource treats that as a
        // dropped connection and auto-reconnects — which replays the whole
        // run again (replay always restarts from event 0, and even the live
        // endpoint would re-poll pointlessly). Closing here, the moment the
        // terminal event is seen, is what actually stops the loop.
        if (event.type === "done") {
          source.close();
          setConnected(false);
        }
      } catch {
        // A malformed frame must not kill the stream.
      }
    };
    return () => source.close();
  }, [url]);

  return { state, connected, reset: () => dispatch("reset") };
}
