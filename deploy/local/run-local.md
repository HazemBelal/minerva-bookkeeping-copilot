# Running the full stack locally, published via ngrok (SSE-safe)

This is the demo path: everything runs natively on your machine (Ollama,
backend, frontend), and an ngrok tunnel exposes port 3000 publicly. Use this
instead of the VPS deploy in `deploy/deploy.sh` when the app needs a local
vision-capable Ollama model that the VPS can't host.

**Why ngrok and not Cloudflare:** a Cloudflare quick tunnel (`cloudflared
tunnel --url ...`) buffers Server-Sent Events — plain HTTP requests pass
through fine, but `/sse/*` responses never arrive incrementally, they arrive
in one batch at the end (or time out). Since the whole UI is driven by SSE,
that freezes the page. ngrok with `--host-header=rewrite` streams SSE
correctly (proven below). `tools/cloudflared.exe` is still in the repo as a
fallback but is NOT the supported path for this app.

## Prerequisites

- **Ollama** running on the host at `http://localhost:11434`, with the
  vision model pulled: `ollama pull qwen2.5vl:7b`. Verify: `curl
  http://127.0.0.1:11434/api/tags` lists it.
- **Backend venv**: `backend/.venv` built with `backend/requirements.txt`
  (includes browser-use + playwright; run `playwright install chromium`
  once inside the venv if it's a fresh checkout).
- **`backend/.env`** present (gitignored, not committed) with at least:
  ```
  LLM_BASE_URL=http://localhost:11434/v1
  LLM_MODEL=qwen2.5vl:7b
  LLM_API_KEY=ollama
  LLM_USE_VISION=true
  RUNS_DIR=runs
  MAX_STEPS_PER_MERCHANT=6
  MAX_MERCHANTS=8
  CONCURRENCY=2
  RUNS_PER_IP_PER_HOUR=3
  ```
- **Node.js** (for `npm run build` / `npm run start` in `frontend/`).
- **ngrok** binary at `tools/ngrok.exe` (gitignored — not committed) with an
  authtoken configured (`ngrok config add-authtoken <token>`) and the
  account's **email verified** at dashboard.ngrok.com/user/settings. An
  unverified email makes ngrok serve an "Email verification required"
  interstitial for every request instead of your app.

## Bring up the stack

Run each in its own terminal (or background them) from the repo root
`C:\D\repos\minerva-bookkeeping-copilot`.

**1. Ollama** — already running as a host service; nothing to start.

**2. Backend** (port 8000):
```
cd backend
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**3. Frontend** (production build, port 3000):
```
cd frontend
npm run build
npm run start
```
`frontend/next.config.ts` rewrites `/api/*`, `/sse/*`, `/shots/*` to
`127.0.0.1:8000`, and sets `compress: false` so Next's own gzip layer can't
buffer the proxied SSE stream. Use `127.0.0.1` everywhere, not `localhost`
— `localhost` can resolve to IPv6 `::1` and miss an IPv4-only listener.

**4. ngrok tunnel** (public URL to port 3000):
```
./tools/ngrok.exe http --host-header=rewrite 127.0.0.1:3000
```
`--host-header=rewrite` is required — without it the origin sees the
tunnel's Host header and 400s.

## Read the current public URL

ngrok exposes a local API on `127.0.0.1:4040`:
```
curl -s http://127.0.0.1:4040/api/tunnels
```
Take `tunnels[0].public_url` (an `https://...ngrok-free.dev` URL). That's
the link to send.

## Smoke test before sharing the link

```
curl 127.0.0.1:8000/api/health          # backend direct
curl 127.0.0.1:3000                      # frontend serving
curl 127.0.0.1:3000/api/health           # frontend proxies to backend
```
All three should return 200 with the expected JSON/HTML.

## The ngrok interstitial (tell the reviewer about this)

The **first** browser visit to an `ngrok-free.dev` URL shows a one-time
ngrok warning page ("You are about to visit ... Visit Site"). Clicking
"Visit Site" sets a cookie and every subsequent visit from that browser
skips it. This only affects `Accept: text/html` navigations — the app's own
`/api/*` (JSON) and `/sse/*` (event-stream) requests are not affected
(non-browser user agents / `ngrok-skip-browser-warning` header both bypass
it), so once past the one-time click the app works normally, including
streaming. **Mention this in the email/message with the link** so the
reviewer isn't surprised by it.

## Verified end-to-end through the tunnel (2026-08-09)

Public URL for this session: `https://riding-tasting-passerby.ngrok-free.dev`
(ngrok-free URLs are random and change every time the tunnel restarts — see
the reboot caveat below).

- Interstitial observed on first browser visit exactly as described above;
  clicking "Visit Site" landed on the real app (`<title>Bookkeeping
  Copilot</title>`), cold-open auto-replay was already running (rows in
  "researching…" state, amber notice banner, activity feed streaming
  reasoning text, and a live screenshot from `/shots/golden/shots/...`
  rendered in the screenshot panel).
- Triggered a live run: `POST {tunnel}/api/runs` with the sample statement,
  then streamed `GET {tunnel}/sse/runs/{run_id}` with header
  `ngrok-skip-browser-warning: 1`. Events arrived incrementally over the
  full run, not batched — representative timestamps (seconds since the
  POST):
  ```
  [+0.90s]  POST /api/runs -> 201 {"run_id":"381a3159c163"}
  [+1.33s]  SSE connected, status=200
  [+1.33s]  seq=1  reasoning  "Reading the statement."
  [+1.33s]  seq=2  reasoning  "Found 10 transactions. Planning."
  [+11.33s] seq=3  plan       (10-row plan)
  [+12.95s] seq=4-7  row_status/reasoning  (uber eats, gusto -> done; sqsp inv -> researching)
  [+27.06s] seq=10-12 reasoning/action/screenshot (amzn mktp us: google search)
  [+30.09s] seq=13-15 reasoning/action/screenshot (sqsp inv: google search)
  [+41.88s] seq=24-27 reasoning/action/screenshot (amzn mktp us: click result)
  [+55.61s] seq=35-38 reasoning/action/screenshot (amzn mktp us: click link)
  [+60.48s] seq=42-44 action=done (amzn mktp us resolved)
  [+70.28s] seq=49    row_status done (amzn mktp us) -> grain cafe starts researching
  ```
  Gaps of 10-15 real seconds between merchant research steps (actual browser
  navigation/LLM latency) show up as real gaps in arrival time through the
  tunnel — proof the stream isn't buffered and flushed at the end. A batched
  connection would show all seq numbers arriving within milliseconds of each
  other at the very end of the run; this shows them arriving continuously
  across 70+ seconds while the run was still in progress.
- Golden replay screenshot fetched directly through the tunnel:
  `GET {tunnel}/shots/golden/shots/sqsp_inv_3.png` with
  `ngrok-skip-browser-warning: 1` -> `200 image/png 68003 bytes` (matches the
  direct-backend byte count).
- The triggered live run ran to completion entirely through the tunnel
  connection above (server-side execution isn't tied to any one SSE
  client, but the whole trajectory streamed while the client was attached):
  finished at seq 185, `done` event, summary *"10 transactions categorized,
  2 flag(s) raised, 0 row(s) need review."* All 8 unique merchants resolved
  (6 via live web research with real source URLs — Squarespace, Amazon,
  Grain Cafe, Ramp, Mercury, SP Connect/"cordless desk" — and 2 via
  high-confidence model fallback for global brands Uber Eats and Gusto), 2
  `round_amount` flags fired (RAMP 1250.00, MERCURY 5000.00) exactly as
  expected, 0 needs_review, 0 errors. Total wall time first-event to
  `done`: ~245s (~4m), in line with the ~4-minute budget. `GET /api/health`
  through the tunnel afterwards showed `busy:false` and `GET
  /api/runs/latest` still returned `{"run_id":"golden"}` — the completed
  test run does not disturb the golden cold-open a fresh visitor sees,
  since `main.py`'s `/api/runs/latest` always prefers `golden` when present.

## Shutting down

```
taskkill //IM ngrok.exe //F
```
Then stop the backend/frontend processes you started (Ctrl+C in their
terminals, or `taskkill //PID <pid> //F` if backgrounded). Kill stragglers
before a fresh start — a leftover ngrok.exe holding the API port will make
`:4040/api/tunnels` return stale data, and a leftover uvicorn/next process
will make the next `npm run start` or `uvicorn` fail to bind its port.

## Reboot / restart caveat

**The free ngrok URL is random and changes every time the tunnel process
restarts.** There is no fixed subdomain on the free plan. If the backend,
frontend, or ngrok process is restarted for any reason (crash, reboot,
manual redeploy), you MUST:
1. Re-run `curl http://127.0.0.1:4040/api/tunnels` to get the new
   `public_url`.
2. Re-send the new link to whoever needs it — the old link will 404
   (ngrok, not the app, since the tunnel no longer exists).

For a longer-lived stable link, upgrade to an ngrok paid plan (reserved
domain) or fall back to the VPS deploy (`deploy/deploy.sh`), which is
always-on but cannot run the local vision model.
