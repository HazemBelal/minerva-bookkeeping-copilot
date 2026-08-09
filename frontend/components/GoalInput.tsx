"use client";

export function GoalInput({
  goal,
  statement,
  disabled,
  onGoal,
  onStatement,
  onRun,
}: {
  goal: string;
  statement: string;
  disabled: boolean;
  onGoal: (v: string) => void;
  onStatement: (v: string) => void;
  onRun: () => void;
}) {
  return (
    <div className="space-y-3">
      <input
        value={goal}
        onChange={(e) => onGoal(e.target.value)}
        placeholder="What should the agent do?"
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
      />
      <textarea
        value={statement}
        onChange={(e) => onStatement(e.target.value)}
        rows={7}
        spellCheck={false}
        placeholder="Paste bank transactions: date, description, amount"
        className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs"
      />
      <button
        onClick={onRun}
        disabled={disabled || !statement.trim()}
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        Run the agent
      </button>
    </div>
  );
}
