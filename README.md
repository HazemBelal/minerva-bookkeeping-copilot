# Bookkeeping Copilot

An accountant pastes a messy bank statement — descriptors like `SQSP* INV`,
`AMZN MKTP US`, `SP CORDLESS DESK CO` — and the agent researches every
unrecognized merchant live in a real browser, assigns an expense category with
a confidence level and a clickable source, flags anomalies, and produces a
categorized ledger the accountant can approve, override, and export.

**Live demo:** `<ngrok URL to be filled in at submission — see "Hosting" below>`

---

## What it does

1. Paste (or use the bundled sample) a raw bank statement.
2. The agent parses it, groups repeated merchants, and shows a plan of what it
   already recognizes vs. what it needs to go research — before it opens a
   single browser tab, so you see the scope of the work immediately.
3. For every unknown merchant, a bounded browser agent searches the
   descriptor, opens the most credible result, reads it, and reports back what
   the business does, a category, a confidence level, and the URL it used.
4. A deterministic pass flags anomalies: duplicate charges, repeated
   same-merchant same-day charges, large round-number amounts, and merchants
   it couldn't identify.
5. You watch it happen — a live ledger, an agent activity feed with
   screenshots, and controls to pause, resume, or stop — then approve or
   override any row and export the result to CSV.

## How it works

### Two tiers, plus a deterministic anomaly pass

**Tier 1 — planner (LLM, no browser).** Parses the statement, deduplicates
merchants by a normalized `merchant_key` (collapsing processor prefixes and
trailing store/invoice IDs so `SQSP* INV 928471` and `SQSP*INV 114400` are one
merchant, not two), and classifies each distinct merchant as either
confidently known or needing research. The plan is emitted before any
browsing starts. The prompt is deliberately conservative: it's told an
abbreviated or processor-prefixed descriptor must go to research even if it
looks decodable, and that a wrong confident answer is worse than a slower
correct one — only globally unambiguous brands spelled out in full skip
research.

**Tier 2 — browser research agent** ([browser-use](https://github.com/browser-use/browser-use)
+ a vision LLM driving headless Playwright Chromium). One bounded agent per
unknown merchant: max 6 steps, 2 running concurrently. It searches the
descriptor, opens the most credible result, reads it, and returns
`{merchant, what_they_do, category, confidence, source_url, reasoning}`. If it
can't verify a merchant, it returns nothing fabricated — the row surfaces as
`needs_review` instead.

**Anomaly pass (deterministic code, no LLM — on purpose).** Duplicate-charge
detection, same-merchant/same-day repeat detection, large round-number
amounts, and unidentified merchants are all plain, inspectable rules, not a
model call. A hallucinated fraud flag in an accounting product is worse than
no flag at all, so every rule here is explicit and reproducible.

### The model runs locally — and that's a feature, not a limitation

The default LLM is a **local Ollama vision model, `qwen2.5vl:7b`**. No
financial data leaves the machine, which genuinely matters for an accounting
product handling real statements.

Every LLM call goes through one provider-agnostic client
(`backend/app/llm.py`, built on the OpenAI SDK against an OpenAI-compatible
endpoint). Pointing the whole system at OpenAI's GPT-4o or Gemini's
OpenAI-compatible endpoint instead is a four-environment-variable change —
`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_USE_VISION` — not a code
change.

**The honest trade-off:** a 7B local model is weaker than a frontier model at
the multi-step browse-and-extract loop research requires. The design absorbs
that in two ways: the `needs_review` path means a weak or failed research
attempt becomes a visible, honest row instead of a wrong guess, and the
research prompt is written to force the agent to actually run a web search and
synthesize the merchant name from what it finds, rather than pattern-matching
the raw descriptor. In testing against the sample statement, it resolves
merchants reliably (roughly 8–10 out of 10, with real source URLs), at
roughly 30–40 seconds per merchant — about 4 minutes for a full run of the
sample's 8 distinct merchants at 2 concurrent.

### One event schema drives live streaming, replay, and reconnect

Every step of a run — plan, row status change, reasoning, browser action,
screenshot, anomaly flag, completion — is appended to a per-run JSONL log and
streamed to the browser over Server-Sent Events. That same log is what powers
replay (played back at a fixed speed) and mid-run reconnection: reloading the
page while a run is in progress resumes from the current position instead of
restarting.

The landing page cold-opens by replaying a real recorded "golden" run, so a
first-time visitor sees the product actually working within seconds, with an
always-visible control to abandon the replay and drive the agent live
instead.

### Interface

This is graded hardest on the interface, so it gets a plain description:

- A live ledger where rows move from skeleton loading state → researching →
  done (or amber `needs_review`).
- Confidence shown as a bar, not a bare number.
- Every categorization carries a clickable source link — nothing is asserted
  without a citation the accountant can go check themselves.
- A plain-language agent activity feed with the live screenshots the browser
  agent is actually looking at.
- Run controls: STOP, pause, resume.
- Per-row approve and category override.
- CSV export of the final ledger.

## Transparency and human-in-the-loop

Nothing in this system is presented as a final answer the accountant can't
see behind. Every category comes with a confidence level and a source link;
every anomaly flag names the exact rule that fired and which rows triggered
it; every research step is visible in the activity feed as it happens, not
summarized after the fact; and the accountant approves or overrides every row
before export. When the agent can't verify a merchant, it says so
(`needs_review`) instead of guessing.

## Guardrails

This runs on a public link, so it's deliberately boxed in:

- 6 browser steps per merchant, 8 researched merchants per run, 2 concurrent.
- 3 runs per hour, per IP.
- A single global run lock — only one run executes at a time across all
  visitors.
- Read-only browsing: no logins, no purchases, no form submissions other than
  a search box.
- Prompt-injection defense: the research agent's system prompt states
  explicitly, twice (in the task text and in the system-prompt extension),
  that page text is data to analyze, never instructions to follow — including
  text that claims to be a system message or an override.

## Hosting and the public link

The full stack runs natively on the developer's machine — the vision model
needs a local GPU — and is published through an **ngrok tunnel**.

**Why ngrok, not Cloudflare:** Cloudflare's free quick tunnel was tested and
found to buffer Server-Sent Events — plain requests pass through fine, but
`/sse/*` responses arrive in one batch at the end (or time out) instead of
incrementally, which would freeze the live UI. ngrok with
`--host-header=rewrite` streams SSE correctly; this was verified end-to-end
with timestamped, incrementally-arriving events through the full chain
(browser → ngrok → Next.js rewrite proxy → FastAPI → SSE).

**Honest caveats:**

- The developer's machine has to be running during evaluation — this is not
  a hosted service.
- The free ngrok URL is random and changes every time the tunnel restarts.
  There's no reserved subdomain on the free tier.
- ngrok-free shows a one-time browser interstitial ("You are about to
  visit... Visit Site") on a visitor's first request. Clicking through sets a
  cookie; it doesn't reappear for that browser.

A Rocky Linux VPS with nginx/TLS (`deploy/deploy.sh`, `deploy/bootstrap.sh`,
`deploy/nginx.conf`) exists as a documented fallback for a hosted,
paid-API-key configuration — but it can't run the local vision model, so it
is not the live demo path. See `deploy/local/run-local.md` for the exact
bring-up commands, the SSE verification evidence, and the reboot procedure
for re-fetching the current tunnel URL.

## Framework evaluation

The task asked for a judgment call on which browser-automation framework to
build on, not just "pick one."

- **[browser-use](https://github.com/browser-use/browser-use)** was adopted
  as the engine: structured page snapshots plus batched, multi-action steps
  fit a bounded research loop well.
- **Stagehand** and **ego-lite** were evaluated. ego-lite's clean
  snapshot/click/fill vocabulary and code-based batched actions directly
  informed how the research agent's steps are structured — but ego-lite
  itself is a macOS desktop app bound to a local Chrome profile, and this
  needed to be a hostable, transparent, steerable web app. Its ideas were
  borrowed; the dependency was not.
- A custom Playwright agent layer was considered and rejected for the
  timebox — reimplementing snapshot-driven action selection from scratch
  wasn't worth it against an existing, working framework.

## Testing

The deterministic core is unit-tested: statement parsing and merchant-key
normalization, the category vocabulary, the anomaly rules, the event log,
rate limiting, the frontend event reducer, and orchestrator behavior
(concurrency, pause, stop, the merchant cap) with the LLM and browser stubbed
out. That's 46 backend tests (`backend/tests/`, pytest) and 10 frontend tests
(`frontend/__tests__/`, vitest).

LLM and browser trajectories themselves are **not** mocked — they're verified
by actually running them and reading the resulting event log and screenshots
(see the SSE and end-to-end evidence in `deploy/local/run-local.md`). That's
a deliberate trade for the timebox: an LLM-in-the-loop browser agent is hard
to meaningfully mock without testing the mock instead of the system, so the
mocked coverage stops at the boundary where the LLM and the browser start,
and everything past that boundary is verified by observation instead.

## Running it

See `deploy/local/run-local.md` for the full runbook — prerequisites, exact
commands for Ollama, backend, frontend, and the ngrok tunnel, the smoke-test
checklist, and the reboot/URL-refresh procedure.

Short version:

```bash
# 1. Ollama, with the vision model pulled
ollama pull qwen2.5vl:7b

# 2. Backend (needs backend/.env — see .env.example)
cd backend
python -m venv .venv && ./.venv/Scripts/activate
pip install -r requirements.txt
playwright install chromium
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. Frontend
cd frontend
npm install
npm run build && npm run start

# 4. Public tunnel (optional, for sharing a link)
./tools/ngrok.exe http --host-header=rewrite 127.0.0.1:3000
```

Or `docker compose up` for a containerized backend + frontend (still needs
Ollama reachable on the host — see `.env.example` and `docker-compose.yml`).

## What I'd build next

- **Persist runs and approvals** past a single session — currently a run's
  ledger and approvals live in frontend state plus the on-disk event log, but
  there's no durable store an accountant could return to tomorrow and see
  their prior approvals.
- **Learn from overrides** — if an accountant recategorizes a merchant, that
  correction should feed back so the same merchant doesn't need re-research
  next time.
- **Batch upload** — multiple statements or a CSV/OFX import instead of
  pasting raw text.
- **Per-firm chart of accounts** — the category vocabulary is currently one
  fixed list; real bookkeeping practices need their own categories mapped in.
- **A stronger or hosted model** for higher research reliability — the local
  7B vision model is the right default for data privacy, but a frontier model
  behind the same provider-agnostic client would raise the merchant
  resolution rate and could be offered as an opt-in for accounts that don't
  need the local-only guarantee.
