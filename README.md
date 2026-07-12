# ReplaysAI

ReplaysAI turns real NBA and NFL data into a personalized, agent-driven sports desk: a streaming
feed, narrated highlight reels, a two-host AI broadcast, a real pick'em ladder, and a personalized
weekly newsletter, all keyed to the teams and players you pick, with no signup.

Everything a fan consumes as fact (players, games, scores, play-by-play, box scores, season stats,
news, highlight clips) is real, live ESPN public-API data. Generated prose (recaps, reel narration,
newsletter, broadcast) is grounded strictly in that data, and the UI labels which engine produced it
(trained model, general LLM, or deterministic template).

---

## The product surfaces

| Surface | Route | What it does |
|---|---|---|
| **Cinematic landing** | `/` | A live `<canvas>` broadcast hero with four named agents overlaying tracking, stats, rule reads, and a ticking win-probability. |
| **Onboarding** | `/demo` | Pick leagues, teams, and star players. Stored anonymously in `localStorage`. No account. |
| **Dashboard** | `/feed` | Upcoming games, your stars' season lines, recent results, standings / leaders / tailored-news rail. Analysis (predictions, what-ifs, player stats) collapses behind "More analysis." |
| **Season** | `/season` | The full last-10-seasons game list for your teams plus per-team form charts. |
| **Stats** | `/stats` | A stats browser scoped to your teams' rosters (real ESPN season stats), by position. |
| **Extras** | `/extras` | A **real** pick'em board, fantasy roster builder, the **live leaderboard**, and your points / streak / badges. |
| **Reels** | `/reels` -> `/reel/:gameId` | Tiered narrated highlight reels (2m / 5m / 10m) from real ESPN clips, voiced by TTS over ducked clip audio, with interrupt-and-ask. |
| **Broadcast** | `/broadcast/:gameId` | A two-host AI broadcast (play-by-play + analyst) synced to the story player. |
| **Newsletter** | `/newsletter` -> `/newsletter/share/:token` | A personalized weekly digest, curated by a learned ranker and written by the newsletter agent. Shareable by real link. |
| **Game detail** | `/game/:id` | LLM recap, your-team "fan" recap, highlight reel, and play-by-play. |
| **Player** | `/player/:id` | A followed player's real season line and profile. |

---

## Architecture

```
                          Browser (Vite + React 19)
   anonymous device id in localStorage · TanStack Query · React Router 7
                        │  /api/*  (X-Device-Id header; Vite dev-proxy -> :8001)
                        ▼
                    FastAPI app (app.py -> routers)
   ┌──────────────────────────────────────────────────────────────────────┐
   │ feed · games · recaps · reels · broadcast · chat · predictions ·      │
   │ rankings · fantasy · leaderboard · news · insights · newsletter       │
   └──────────┬───────────────────────┬────────────────────┬──────────────┘
              │                        │                    │
     SportsData (espn_public.py)   Redis store (db/store)   LLM / trained agents
   real ESPN endpoints, NBA+NFL   picks · points ·         newsletter + broadcast:
   in-memory (60s) + Redis cache  leaderboard ·            trained model -> Anthropic
   teams·games·plays·box·clips    newsletter share         -> deterministic fallback
```

### Backend: FastAPI, stateless functions
- `app.py` composes the routers; `main.py` / `api/index.py` expose `app` for Vercel.
- **`espn_public.py` is the single `SportsDataProvider`.** Every ESPN call lives here behind small
  typed functions. Swapping data sources means reimplementing this one module.
- **Two-tier cache:** a process-local dict (60s TTL) plus optional Redis. Both degrade silently.

### Identity and persistence: anonymous, login-free, real
- Identity is an anonymous **device id** (one UUID per browser, `lib/device.ts`), sent as the
  `X-Device-Id` header and resolved by `middleware/identity.py`. No auth provider, no PII.
- **`db/store.py`** is a small Redis-backed store (Upstash / Vercel KV via `REDIS_URL`). It makes
  picks, points, streaks, badges, the leaderboard, and newsletter share links **real and durable**.
  Picks are scored lazily: when a picked game finishes (both scores present), the pick resolves on
  the next read and points flow to the leaderboard sorted set. With no `REDIS_URL`, every store call
  degrades to a no-op so local dev and the zero-config demo still run.

### LLM and trained agents
- General LLM path (`api/recaps.py:llm_text`): Anthropic first (`claude-haiku-4-5` -> Sonnet),
  then OpenAI, then a deterministic, data-backed fallback. Every LLM feature works with zero keys.
- **Trained agents** for the two flagship writers. The **newsletter** and **broadcast** surfaces
  call our own fine-tuned open models over an OpenAI-compatible API (`recaps.py:trained_text`), and
  fall back to the general LLM and then the template. The newsletter's content is ordered by a
  learned **curation ranker** (`api/curation.py`, pure-Python inference). See
  [`training/`](training/README.md) for the dataset, distillation, LoRA fine-tune, and ranker
  training. Until the models are trained and configured, these surfaces run on the LLM/template and
  the heuristic ranker, and the API reports which engine ran (`source`, `curation`).

### Frontend: Vite + React 19
- React Router 7 with a tabbed `Feed` shell plus dedicated routes for the heavy surfaces.
- **TanStack Query** owns server state; **`localStorage`** owns the anonymous team/player picks; the
  device id keys the server-side earned state (points, leaderboard).
- Reels/broadcast are voiced with `speechSynthesis` and accept voice input via `SpeechRecognition`.
  The landing hero is a `requestAnimationFrame` canvas with a `prefers-reduced-motion` fallback.

---

## Data provenance and honesty
Real, live ESPN data: players, teams, games, scores, play-by-play, box scores, season stats,
standings, leaders, news, and highlight clips. Generated text is grounded only in that data. The UI
never claims a model that did not run: the newsletter footer and API responses label the engine as
**trained**, **LLM**, or **deterministic**, and the curation ranker as **trained** or **heuristic**.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, httpx, Pydantic |
| Data | ESPN public API (NBA + NFL, no key) |
| Store | Redis (Upstash / Vercel KV): picks, points, leaderboard, newsletter share |
| LLM | Anthropic `claude-haiku-4-5` (+ Sonnet); OpenAI optional; deterministic fallback |
| Trained agents | Fine-tuned open model (GPT-OSS / Qwen / DeepSeek) on Baseten, OpenAI-compatible |
| Frontend | React 19, TypeScript, Vite, React Router 7, TanStack Query, react-markdown, hls.js |
| Deploy | Vercel (serverless functions + static frontend) |

---

## Environment
No keys are required. See `.env.example`. Highlights:

| Env var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | General LLM (recaps, reels, chat, newsletter/broadcast fallback) |
| `OPENAI_API_KEY` | Optional LLM fallback |
| `REDIS_URL` | Durable store: real picks, leaderboard, gamification, newsletter share |
| `TRAINED_BASE_URL` / `TRAINED_API_KEY` / `NEWSLETTER_MODEL` / `BROADCAST_MODEL` | Trained newsletter + broadcast writers (see `training/`) |
| `ALLOWED_ORIGINS` | CORS origins (default localhost:5173/3000) |

---

## Getting started

**Prerequisites:** Python 3.12, Node 18+.

```bash
# 1. Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional: add keys / REDIS_URL to enable AI + persistence
uvicorn app:app --reload --port 8001

# 2. Frontend (separate shell)
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api -> :8001
```

Training the agents is a separate offline workflow: see [`training/README.md`](training/README.md).

---

## Project structure

```
ReplaysAI/
├── app.py / main.py         # FastAPI app factory + Vercel entrypoint
├── config.py                # settings + LLM / trained-model config
├── api/
│   ├── espn_public.py       # SportsDataProvider: all ESPN calls + caching
│   ├── feed.py · games.py · recaps.py · rankings.py · news.py · insights.py
│   ├── predictions.py       # real pick'em: store picks, score on finish
│   ├── leaderboards.py      # real leaderboard from the Redis sorted set
│   ├── auth.py              # anonymous device profile (points/streak/badges)
│   ├── reels.py · broadcast.py  # narrated reels + two-host broadcast (trained-first)
│   ├── newsletter.py        # curated + written weekly digest (trained-first)
│   └── curation.py          # learned newsletter curation ranker (pure-Python inference)
├── db/store.py              # Redis store: picks, points, leaderboard, newsletter share
├── middleware/identity.py   # anonymous device-id identity
├── cache/redis_client.py    # optional JSON cache with TTL
├── training/                # OFFLINE: dataset, distillation, LoRA, curation ranker, eval
└── frontend/src/            # pages, components, hooks, lib
```
