# Bookkeeping Copilot — Frontend

This is the frontend for **Bookkeeping Copilot**. See the root
[`README.md`](../README.md) for the project overview, and
[`deploy/local/run-local.md`](../deploy/local/run-local.md) for how to run
the full stack (backend + Ollama + this app) locally.

It's a Next.js (App Router) + TypeScript + Tailwind app. It talks to the
FastAPI backend same-origin, via `/api` (REST) and `/sse` (streaming run
events) — both proxied to the backend in `next.config.ts`.

```bash
npm install
npm run dev
```
