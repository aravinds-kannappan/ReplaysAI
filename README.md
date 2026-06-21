# ReplaysAI

ReplaysAI turns real NBA & NFL data into a **personalized, agent-driven sports desk**: a streaming
feed, narrated highlight reels you can interrupt and ask questions during, a Monte-Carlo "dream
team" championship simulator, and AI game recaps — all keyed to the teams and players you pick, with
**no signup**.

Everything a fan consumes as fact (players, games, scores, play-by-play, box scores, season stats,
news, highlight clips) is **real, live ESPN public-API data**. The only modeled elements are clearly
labeled as such: the championship simulation is a forecast, and the landing-page court animation is
illustrative.

---

## The product surfaces

| Surface | Route | What it does |
|---|---|---|
| **Cinematic landing** | `/` | A live `<canvas>` broadcast hero — players drift, a ball passes with a glowing trail, a scan line sweeps, and four named agents (**ScoutAgent / StatAgent / RefAgent / PredictAgent**) overlay tracking, stats, rule reads, and a ticking win-probability. |
| **Onboarding** | `/onboarding` | Pick leagues → teams → star players. Stored anonymously in `localStorage`. No account. |
| **Dashboard** | `/feed` | Daily AI brief, upcoming games for your teams, your stars' season lines, recent results, and a standings / leaders / tailored-news rail. Heavy analytics collapse behind "More analysis." |
| **Season** | `/season` | The full last-10-seasons game list for your teams plus per-team form charts. |
| **Reels** | `/reels` → `/reel/:gameId` | Tiered narrated highlight reels (Pulse 2m / Story 5m / Deep Cut 10m) from **real ESPN clips**, voiced by TTS over ducked clip audio, with stat overlays and **interrupt-and-ask** (pause, ask the analyst by mic or text, resume). |
| **Dream Team** | `/dream-team` | Draft real stars → server-side **10,000-season Monte-Carlo** → championship odds, projected record, playoff-round chart, a CoachAgent chemistry read, an AnalystAgent X-factor, and a shareable PNG card. |
| **Game detail** | `/game/:id` | LLM recap, your-team "fan" recap, highlight reel, and play-by-play. |
| **Extras** | `/extras` | Pick'em board, fantasy roster builder, leaderboard preview. |

---

## Architecture

```
                          Browser (Vite + React 19)
   anonymous identity in localStorage · TanStack Query · React Router 7
                                   │  /api/*  (Vite dev-proxy → :8001)
                                   ▼
                       FastAPI app  (app.py → routers)
   ┌───────────────────────────────────────────────────────────────────┐
   │  feed · games · recaps · reels · chat · dream_team · rankings ·    │
   │  predictions · fantasy · news · insights · leaderboards · waitlist │
   └───────────────┬───────────────────────────────┬───────────────────┘
                   │                                │
        SportsData (espn_public.py)         LLM layer (Anthropic-first)
   real ESPN endpoints, NBA + NFL           claude-opus-4-8
   in-memory (60s) + Redis cache            → sonnet-4-6 → haiku-4-5
   teams · games · plays · box · clips      → openai gpt-4o-mini
                                            → deterministic data fallback
```

### Backend — FastAPI, stateless, serverless-friendly
- `app.py` composes ~14 routers; `main.py` exposes `app` for Vercel.
- **No database.** All state is either fetched from ESPN, cached, or stored client-side. This keeps
  the API stateless and deployable as serverless functions.
- **`espn_public.py` is the single `SportsDataProvider`** — every ESPN call lives here behind small
  typed functions (`fetch_espn_games`, `fetch_espn_game_summary`, `extract_summary_videos`,
  `fetch_espn_athlete_stats`, …). Swapping data sources means reimplementing this one module.
- **Two-tier cache:** a process-local dict with a 60s TTL (warm serverless instances) plus optional
  Redis (`cache/redis_client.py`). Both degrade silently to "no cache" when absent — nothing in the
  request path requires Redis.

### LLM layer — Anthropic-first with graceful degradation
- Primary model `claude-opus-4-8`, falling back through `claude-sonnet-4-6` → `claude-haiku-4-5`,
  then to OpenAI `gpt-4o-mini` if only that key is present (`config.py:anthropic_models`).
- **Every LLM path has a deterministic, data-backed fallback.** Recaps, reel narration, the dream-team
  CoachAgent/AnalystAgent, and the in-app assistant all produce a grounded response with **zero API
  keys configured** — the app never hard-fails on a missing/timed-out model.
- Anti-hallucination is enforced in the system prompts: agents are told to ground strictly in the
  supplied facts and never invent plays, stats, or scores.

### Agents (LLM-backed roles, not microservices)
- **Recap** (`recaps.py`) — beat-writer recap from period scores, leaders, and weighted key plays.
- **Reel director / voice** (`reels.py`) — ranks real clips, writes per-clip narration, builds a
  conversational custom reel, and attaches stat overlays.
- **CoachAgent / AnalystAgent** (`dream_team.py`) — chemistry modifier and X-factor for the sim.
- **In-reel / dashboard assistant** (`chat.py`) — coordinates specialist perspectives; in a reel it
  answers about the exact paused clip using `{gameId, segmentId, clipTimestamp, recentNarration}`.

### Frontend — Vite + React 19
- React Router 7 with a single tabbed `Feed` shell (`/feed`, `/season`, `/reels`, `/extras`) plus
  dedicated routes for the heavy surfaces (`/dream-team`, `/reel/:gameId`, `/game/:id`).
- **TanStack Query** owns server state; **`localStorage`** owns the anonymous fan profile (teams,
  players, picks, rosters). No auth provider is required.
- Reels are voiced with the browser **`speechSynthesis`** API and accept voice input via
  **`SpeechRecognition`**; the dream-team card exports via `html-to-image`. The landing hero is a
  `requestAnimationFrame` canvas animation (with a `prefers-reduced-motion` static fallback).

---

## System design notes

**Independent, streamable endpoints.** Feed tiles, reel tiers, recaps, and sim results are separate
endpoints so the UI fills in progressively rather than blocking on the slowest agent. Query keys are
derived from the personalization inputs, so React Query caches per-fan.

**Recap keyed off the scoreline, not the status string.** ESPN's by-id endpoint is unreliable — it
sometimes labels a finished game (with a final score) as `"scheduled"`. Recaps and the reel game-list
therefore treat **"both scores present" as played**, so finished games reliably get the full LLM
recap and appear as reel-able past games even in the offseason. Truly future games (null scores) get
a clean preview instead.

**Monte-Carlo dream team.** `dream_team.py` derives a per-player rating vector from real ESPN season
stats, applies a chemistry multiplier from the CoachAgent, then runs 10,000 pure-Python seasons:
each draws form noise, a normal-approximated win total, a playoff seed, and a round-by-round bracket.
Output is championship odds, projected record, and a playoff-round distribution. A league-average
overall maps to ~0.5 strength so an elite roster is dominant but believable (~65-70 wins, not 82),
and the RNG is seeded so identical rosters are reproducible. Results cache by a roster signature.

**Reel pipeline (rights-safe MVP).** Clips are **real ESPN highlight video** ranked by importance ×
keyword relevance and spread across the game for the chosen time budget; narration is generated text
spoken client-side; overlays (scorebug, leader stat line, a model win-probability that climbs to the
winner) are attached server-side. The player ducks clip audio under narration and supports
interrupt-and-ask against the same chat endpoint the dashboard uses.

**Player-stats coverage.** Followed players can come from a team's roster (below the top of the
leaderboard), so `fetch_espn_athlete_stats` scans deep enough to cover them and falls back to a
broader stat-label set; deep-bench players with no recorded minutes show a graceful "updates as games
post" state rather than a hard blank.

---

## Tradeoffs (deliberate, and what they cost)

| Decision | Why | Cost / follow-up |
|---|---|---|
| **No database; `localStorage` identity** | Stateless, zero-ops, instant onboarding, no PII | Profiles don't sync across devices; global leaderboards need a real store. (deviceId + JSON export/import is the planned next step.) |
| **Real ESPN clips, not generated video** | Rights-safe and ships today | Can't synthesize plays that lack published video. A `ClipProvider`-style swap-in for AI tactical-diagram clips is the planned upgrade. |
| **Browser TTS, not a Gateway voice** | No backend audio infra; works offline of any TTS vendor | Voice quality is the device's; true SSE streaming + server-side TTS is a follow-up. The segment DTO already carries the narration text for that swap. |
| **Non-streaming `/api/chat` for interrupt-and-ask** | Reuses the existing, well-tested assistant | No token-by-token streaming or server tool-calling yet; the reel context is passed as compact structured text. |
| **10k seasons in pure Python (no numpy)** | Keeps the serverless image small; ~sub-second | Heavier sims would want vectorization; mitigated by Redis caching on a roster signature. |
| **Anthropic-first with full fallback chain** | Best quality when keys exist, never a hard fail | A deterministic recap/narration is lower-fidelity than the model output. |
| **Competition (share codes, Dream-Team League)** | Scoped out of the current build | Leaderboard is a local preview until a durable store is added. |

---

## Data provenance

Real, live ESPN data: players, teams, games, scores, play-by-play, box scores, season stats,
standings, leaders, news, and highlight clips. LLM text (recaps, narration, X-factor, chat) is
AI-written prose grounded only in that real data. **Modeled / illustrative** (and labeled as such in
the UI): the dream-team simulation outputs (a forecast from real ratings) and the landing-page court
animation (stylized — the free ESPN feed has no x/y player-tracking coordinates).

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, httpx, Pydantic |
| Data | ESPN public API (NBA + NFL, no key) |
| LLM | Anthropic `claude-opus-4-8` (+ Sonnet/Haiku fallback); OpenAI `gpt-4o-mini` optional |
| Cache | In-memory (60s TTL) + optional Redis 7 |
| Frontend | React 19, TypeScript, Vite, React Router 7, TanStack Query, react-markdown, hls.js, html-to-image |
| Voice | Browser `speechSynthesis` / `SpeechRecognition` |
| Deploy | Vercel (serverless functions + static frontend) |

---

## Environment

No keys are required to run — the app degrades to data-backed responses. To enable the AI features:

| Env var | Required? | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | recommended | Primary LLM (recaps, narration, sim agents, chat) |
| `OPENAI_API_KEY` | optional | Fallback provider when no Anthropic key |
| `REDIS_URL` | optional | Cross-instance cache for standings, recaps, sims |
| `ALLOWED_ORIGINS` | optional | CORS origins (default localhost:5173/3000) |
| `VITE_API_BASE_URL` | optional (frontend) | Empty for same-origin; set when API is on another origin |

There is **no auth provider requirement** — the app is anonymous by default; the Clerk middleware
remains as an optional pass-through and is not needed to run.

---

## Getting started

**Prerequisites:** Python 3.12, Node 18+.

```bash
# 1. Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY to enable AI (optional)
uvicorn app:app --reload --port 8001

# 2. Frontend (separate shell)
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api → :8001
```

Open `http://localhost:5173`, pick teams/players, and the feed, reels, recaps, and dream-team
simulator populate from real ESPN data.

---

## Project structure

```
ReplaysAI/
├── app.py                  # FastAPI app factory + router registration
├── main.py                 # Vercel entrypoint (exports `app`)
├── config.py               # Pydantic settings + model fallback chain
├── api/
│   ├── espn_public.py      # SportsDataProvider — all ESPN calls + caching
│   ├── feed.py             # /api/feed (favorite-team filtered) + fan recaps
│   ├── games.py            # games list/detail/plays/highlights
│   ├── recaps.py           # llm_text() + recap pipeline (scoreline-keyed)
│   ├── reels.py            # tiered real-clip reels, overlays, conversational director
│   ├── dream_team.py       # rating vectors + CoachAgent + 10k Monte Carlo + AnalystAgent
│   ├── chat.py             # assistant + in-reel interrupt-and-ask context
│   ├── rankings.py         # standings, team stars, player stats
│   ├── predictions.py · fantasy.py · news.py · insights.py · leaderboards.py · waitlist.py
├── cache/redis_client.py   # optional JSON cache with TTL
├── middleware/clerk_auth.py# optional guest-by-default auth
├── frontend/src/
│   ├── pages/              # Landing, Onboarding, Feed, DreamTeam, ReelStudio, GameDetail, …
│   ├── components/         # ReelPlayer (voiced), ScoreCard, Navbar, FloatingAssistant, …
│   ├── hooks/              # useUser (localStorage identity), usePredictions, useGames
│   └── lib/                # api base, auth (no-op guest)
└── requirements.txt
```
