export type EventType =
  | "plan"
  | "row_status"
  | "reasoning"
  | "action"
  | "screenshot"
  | "flag"
  | "error"
  | "done";

export interface RunEvent {
  run_id: string;
  seq: number;
  ts: number;
  type: EventType;
  payload: Record<string, any>;
}

export type Confidence = "high" | "medium" | "low";
export type RowStatus = "pending" | "researching" | "done" | "needs_review";

export interface Row {
  id: number;
  date: string;
  description: string;
  amount: number;
  merchant_key: string;
  merchant: string | null;
  category: string | null;
  confidence: Confidence | null;
  source_url: string | null;
  reasoning: string | null;
  source: "web" | "model" | null;
  status: RowStatus;
  note: string | null;
  flags: string[];
  approved: boolean;
  overridden: boolean;
}

export interface ActivityItem {
  seq: number;
  ts: number;
  kind: "reasoning" | "action" | "error";
  merchant_key: string | null;
  text: string;
}

export type RunStatus =
  | "idle"
  | "running"
  | "paused"
  | "stopped"
  | "done"
  | "error";

export interface RunState {
  runId: string | null;
  status: RunStatus;
  rows: Row[];
  activity: ActivityItem[];
  screenshotUrl: string | null;
  screenshotLabel: string | null;
  error: string | null;
  lastSeq: number;
  summary: string | null;
}
