# Replays AI

**Replays AI** is a personalized, multimodal sports fan platform that combines real play-by-play data ingestion, computer vision, and LLM-powered recap generation with a gamified engagement layer — predictions, leaderboards, fantasy-lite rosters, and fan-perspective recaps written for *your* team.

---

## What it does

Sports media has a content abundance problem: every game generates hours of footage, thousands of structured events, and an audience that wants personalized, contextual highlights — not a broadcast edited for the median fan.

Replays AI closes this gap by ingesting structured play-by-play data, aligning it to raw video via computer vision, and using LLMs to generate recaps that reflect how *a specific fan* watches the game. Then it adds a competitive engagement layer so fans have a reason to come back every day.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy 2.0, asyncio |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| AI / LLM | Anthropic Claude Sonnet 4.6 (text + vision) |
| Sports Data | ESPN unofficial API (NBA + NFL, no key needed) |
| Video | YouTube Data API v3 + yt-dlp + OpenCV |
| Auth | Clerk (JWT-based, React SDK) |
| Frontend | React 18, TypeScript, Vite, TanStack Query, React Router |
| Infra | Docker Compose (or Homebrew for local dev) |

---

## Architecture

### Multi-Agent Inference Pipeline

Three agents run **in parallel** via `asyncio.gather()` — the most expensive steps (CV inference and LLM generation) run concurrently to minimize recap latency:

```
Ingestion (ESPN API — no key needed)
        │
        ▼
   PostgreSQL  ←  games, teams, plays (5M+ row target)
        │
        ├─────────────────────────────────────────────────┐
        │                                                 │
   Agent 1: Event Extraction                    Agent 2: CV Classification
   Pure Python — no LLM needed                  yt-dlp → OpenCV → Claude Vision
   • Scoring runs ≥ 6 pts                        • 1 frame per 3 seconds
   • Lead changes tracking                       • Batched 5 frames/request
   • Clutch moments (final period)               • 14 play type labels
   • Top performer impact scoring                • Confidence scores stored
        │                                                 │
        └──────────────────┬──────────────────────────────┘
                           │
                  Agent 3: LLM Summarization
                  4 parallel Claude Sonnet calls:
                  ┌─────────────┬────────────────┐
                  │ First Half  │  Second Half   │
                  │   Recap     │   & Finish     │
                  ├─────────────┼────────────────┤
                  │  Player     │   Defining     │
                  │ Spotlight   │    Moment      │
                  └─────────────┴────────────────┘
                           │
                     Full Markdown Recap
                           │
                  Agent 4: Fan Perspective (on-demand, cached)
                  • Rewrites recap from your team's POV
                  • Win → celebratory · Loss → honest post-mortem
                  • 1 Claude call, cached permanently per user+game
```

### Caching Strategy

| Data | TTL |
|------|-----|
| Standard recaps | Permanent (immutable once generated) |
| Fan-perspective recaps | Permanent (cached per user + game) |
| Live standings | 5 minutes |

### Database Schema (16 tables)

**Sports core:** `teams` · `players` · `games` · `plays`

**AI outputs:** `game_features` · `cv_classifications` · `recaps` · `fan_recaps`

**User layer:** `users` · `user_favorite_teams` · `user_followed_players` · `predictions` · `user_rosters` · `user_points` · `user_streaks` · `badges` · `user_badges` · `notifications`

---

## Features

### 🤖 AI Recaps
- Generated from real ESPN play-by-play data via 3 parallel agents
- Task-split structure: First Half · Second Half · Player Spotlight · Defining Moment
- Sub-second retrieval from Redis cache after first generation

### 🏀 Fan Mode (Agent 4)
- "My Team's View" tab appears on any game your team played
- Claude rewrites the recap for your team's fans specifically
- Tone shifts dynamically: wins get energy, losses get honest analysis
- Cached permanently after first generation

### 🎯 Predictions
- Pick game winners before tipoff (upcoming games)
- Optional score differential prediction
- Auto-scored when game goes final during ingestion refresh
- **100 pts** for correct winner · **150 pts** for correct + spread within 5

### 🏆 Leaderboard
- Global ranking by total points
- Shows prediction accuracy %, current login streak, badges earned
- Your rank widget when outside top 50

### 📋 Weekly Roster Builder
- Pick up to 8 players per week (NBA or NFL)
- Players sorted by impact score derived from real play-by-play stats
- Roster locks at week start to prevent retroactive changes

### 🔥 Gamification

| Action | Points |
|--------|--------|
| Correct prediction | 100 |
| Correct + spread within 5 pts | 150 |
| Daily login | 5 |
| 7-day login streak bonus | +25 |
| First prediction of week | 10 |

**Badges earned automatically:**

| Badge | Criteria |
|-------|----------|
| 🎯 First Pick | First prediction made |
| 🔮 Oracle | 10 correct predictions |
| 🔥 Loyal Fan | 7-day login streak |
| 🏆 Superfan | 30-day login streak |
| 📊 Analyst | 10 recaps generated |
| ⏱️ Clutch | Correct prediction within 5 pts |

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 16
- Redis 7
- [Anthropic API key](https://console.anthropic.com) — for AI recap + CV generation
- [Clerk account](https://clerk.com) — for authentication

### 1. Clone

```bash
git clone https://github.com/aravinds-kannappan/ReplaysAI.git
cd ReplaysAI
```

### 2. Set up PostgreSQL + Redis

**macOS (Homebrew):**
```bash
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis
createdb replaysai
```

**Docker:**
```bash
docker-compose up -d
```

### 3. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
cp .env.example .env
# Edit .env with your keys (see Environment Variables below)
```

```bash
# Start the API server
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Ingest real game data

```bash
# NBA — fetches last 14 days via ESPN (no API key needed)
PYTHONPATH=. python -m backend.ingestion.nba_ingester

# NFL
PYTHONPATH=. python -m backend.ingestion.nfl_ingester
```

### 5. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:
```env
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

```bash
npm run dev
# → http://localhost:5173
```

---

## Environment Variables

**Backend (`.env`):**

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For AI features | Claude Sonnet API key |
| `CLERK_SECRET_KEY` | For auth | Clerk backend secret |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `YOUTUBE_API_KEY` | Optional | YouTube Data API v3 (falls back to search URL) |

**Frontend (`frontend/.env.local`):**

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key |

---

## API Reference

### Public
```
GET /health
GET /api/games                     ?sport= &status= &date= &limit= &offset=
GET /api/games/{id}
GET /api/games/{id}/plays          ?period= &play_type= &limit=
GET /api/games/{id}/highlights
GET /api/games/{id}/recap
GET /api/rankings                  ?sport=
```

### Auth-required (`Authorization: Bearer <clerk_jwt>`)
```
GET    /api/users/me
PUT    /api/users/me
POST   /api/users/me/teams
DELETE /api/users/me/teams/{team_id}
POST   /api/users/me/players
DELETE /api/users/me/players/{player_id}
GET    /api/users/me/notifications
POST   /api/users/me/notifications/{id}/read

GET    /api/feed
GET    /api/games/{id}/fan-recap
POST   /api/games/{id}/fan-recap/generate
POST   /api/games/{id}/generate

GET    /api/predictions
POST   /api/predictions
GET    /api/predictions/upcoming

GET    /api/rosters
POST   /api/rosters
GET    /api/rosters/players        ?sport=

GET    /api/leaderboard
GET    /api/leaderboard/me
```

---

## Project Structure

```
ReplaysAI/
├── backend/
│   ├── main.py                    # FastAPI app, startup, badge seeding
│   ├── config.py                  # Pydantic settings (reads .env)
│   ├── api/
│   │   ├── auth.py                # /api/users/* — profile + favorites
│   │   ├── feed.py                # /api/feed + /api/games/{id}/fan-recap
│   │   ├── games.py               # /api/games — list, detail, plays, highlights
│   │   ├── recaps.py              # Standard recap generation + cache
│   │   ├── predictions.py         # Prediction CRUD + upcoming games
│   │   ├── fantasy.py             # Weekly roster builder
│   │   ├── rankings.py            # Standings + player profiles
│   │   └── leaderboards.py        # Global + personal rank
│   ├── agents/
│   │   ├── orchestrator.py        # Runs agents 1+2 in parallel, feeds agent 3
│   │   ├── event_extraction.py    # Agent 1: pure Python analytics
│   │   ├── cv_classification.py   # Agent 2: Claude Vision on video frames
│   │   ├── llm_summarization.py   # Agent 3: 4-way task-split recap
│   │   ├── fan_perspective.py     # Agent 4: fan-POV rewrite (on-demand)
│   │   └── prediction_scorer.py   # Scores predictions when game goes final
│   ├── db/
│   │   ├── models.py              # SQLAlchemy ORM — all 16 tables
│   │   └── session.py             # Connection pool (size=10, overflow=20)
│   ├── ingestion/
│   │   ├── nba_ingester.py        # ESPN NBA → PostgreSQL
│   │   └── nfl_ingester.py        # ESPN NFL → PostgreSQL
│   ├── middleware/
│   │   └── clerk_auth.py          # JWT verification + user auto-create
│   ├── video/
│   │   ├── youtube_search.py      # YouTube Data API v3 search
│   │   └── frame_extractor.py     # yt-dlp download + OpenCV frame extraction
│   └── cache/
│       └── redis_client.py        # JSON cache with TTL helpers
├── frontend/src/
│   ├── pages/
│   │   ├── Landing.tsx            # Public marketing page (Sleeper-style)
│   │   ├── Onboarding.tsx         # Team picker post-signup
│   │   ├── Feed.tsx               # Personalized game feed
│   │   ├── GameDetail.tsx         # Recap / Fan Mode / Highlights / Plays tabs
│   │   ├── Predictions.tsx        # Pick winners + history
│   │   ├── Leaderboard.tsx        # Global rankings table
│   │   ├── RosterBuilder.tsx      # Weekly fantasy roster
│   │   └── Profile.tsx            # Badges, stats, notifications
│   ├── components/
│   │   ├── Navbar.tsx             # Sticky nav — auth-aware
│   │   ├── ProtectedRoute.tsx     # Redirects unauthenticated users
│   │   ├── ScoreCard.tsx          # Game score card
│   │   ├── RecapViewer.tsx        # Markdown recap + generate button
│   │   ├── HighlightReel.tsx      # YouTube embed + CV-detected plays timeline
│   │   └── PlayTimeline.tsx       # Play-by-play list with period/type filters
│   └── hooks/
│       ├── useGames.ts            # Game + plays + recap queries
│       ├── useUser.ts             # Clerk-authed user + favorites mutations
│       ├── usePredictions.ts      # Predictions + feed + roster queries
│       └── useLiveScores.ts       # Rankings query
├── docker-compose.yml             # PostgreSQL + Redis services
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment variable template
```

---

## CV Pipeline Details

1. **Video discovery** — searches YouTube: `"{team1} vs {team2} {date} highlights {sport}"`
2. **Download** — yt-dlp at max 480p MP4, audio stripped
3. **Frame extraction** — OpenCV: 1 frame every 3 seconds, max 60 frames per game
4. **Batch inference** — 5 frames per Claude Vision API call (async, parallel batches)
5. **Classification** — 14 play types: `dunk · three_pointer · block · steal · turnover · free_throw · assist · touchdown · interception · field_goal · sack · crowd_reaction · replay · other`
6. **Storage** — `cv_classifications` table with `frame_timestamp` + `confidence` per frame

---

## Roadmap

- [ ] SSE (Server-Sent Events) for live in-game score updates
- [ ] Private prediction leagues between friends
- [ ] Player stat pages with season trends + shot charts
- [ ] Push notifications (web) for prediction results and highlight alerts
- [ ] Mobile app (React Native)
- [ ] Additional sports: WNBA, college football, soccer
- [ ] Draft room for full fantasy leagues
- [ ] Social feed: comment on recaps, react to highlights
