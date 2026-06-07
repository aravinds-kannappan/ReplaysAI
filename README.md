# Replays AI

Replays AI is a personalized sports fan platform that combines real play-by-play data ingestion, computer vision, and LLM-powered recap generation with a gamified engagement layer — predictions, leaderboards, weekly rosters, live dashboards, conversational analysis, and fan-perspective recaps written for your team specifically.

---

## What it does

Sports media has a content abundance problem: every game generates hours of footage, thousands of structured events, and an audience that wants personalized, contextual highlights — not a broadcast edited for the median fan.

Replays AI closes this gap by ingesting structured play-by-play data, aligning it to video via computer vision, and using LLMs to generate recaps that reflect how a specific fan watches the game. The product is now organized around a command center after login: personalized feed, live game stream, assistant chat, predictions, roster outlook, and agent status tabs in one place.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy 2.0, asyncio |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| AI | Anthropic Claude Sonnet 4.6 (text + vision) |
| Sports Data | ESPN unofficial API (NBA + NFL, no key required) |
| Video | YouTube Data API v3, yt-dlp, OpenCV |
| Auth | Clerk (JWT, React SDK) |
| Frontend | React 18, TypeScript, Vite, TanStack Query, React Router |

---

## API / Environment Requirements

Required for production:

| Service | Env var | Why |
|---------|---------|-----|
| Clerk | `VITE_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` | Sign in, protected routes, user profiles, team survey |
| Database | `DATABASE_URL` | Persist users, favorite teams, games, predictions, rosters, recaps |
| Anthropic | `ANTHROPIC_API_KEY` | Dynamic chatbot replies, recap generation, fan-perspective writing, agent narration |

Recommended:

| Service | Env var | Why |
|---------|---------|-----|
| Redis | `REDIS_URL` | Cache standings, recaps, fan recaps, and repeated agent outputs |
| YouTube Data API | `YOUTUBE_API_KEY` | Better highlight/video discovery for reels |

Not required:

| Service | Key needed? | Notes |
|---------|-------------|-------|
| ESPN public data | No | The NBA/NFL team/player fallbacks use public ESPN endpoints with sport/league slugs. |

If `ANTHROPIC_API_KEY` is not set, `/api/chat` returns a setup message instead of pretending to be intelligent.

---

## Architecture

### Multi-Agent Inference Pipeline

Three agents run in parallel via `asyncio.gather()`. The most expensive steps — CV inference and LLM generation — run concurrently to minimize latency.

```
ESPN API
    |
    v
PostgreSQL  <--  games, teams, plays (millions of rows)
    |
    |-- Agent 1: Event Extraction (pure Python, no LLM)
    |   Scoring runs, lead changes, clutch moments, top performers
    |
    |-- Agent 2: CV Classification (Claude Vision)
    |   yt-dlp download -> OpenCV frames -> batch inference
    |   14 play type labels with confidence scores
    |
    v
Agent 3: LLM Summarization (4 parallel Claude calls)
    First half | Second half | Player spotlight | Defining moment
    |
    v
Agent 4: Fan Perspective (on-demand, cached)
    Rewrites recap from your team's point of view
    Win -> celebratory tone. Loss -> honest post-mortem.
```

### Database (17 tables)

Sports core: `teams`, `players`, `games`, `plays`

AI outputs: `game_features`, `cv_classifications`, `recaps`, `fan_recaps`

Player stats: `player_game_stats` (box score per player per game)

User layer: `users`, `user_favorite_teams`, `user_followed_players`, `predictions`, `user_rosters`, `user_points`, `user_streaks`, `badges`, `user_badges`, `notifications`

---

## Features

### Dashboard Command Center
The authenticated app now opens into a tabbed dashboard:

- Feed: personalized games, post-game recap queue, and agent activity
- Reels: computer-vision highlight studio with search rails, moment tags, frame scanning, game attachment, and nested modes for Vision Studio, 2/5/10 minute cuts, and explained reels
- Picks: matchup desk for locking NBA/NFL predictions
- Roster: fantasy arena for drafting players, player duels, and future-season what-if tabs
- Leaders: competitive ladder with global, rivals, and badges tabs
- Global assistant: bottom-right chatbot available across authenticated pages and backed by `/api/chat` with Claude when `ANTHROPIC_API_KEY` is configured

### AI Recaps
Generated from real ESPN play-by-play via 3 parallel agents. Task-split structure: First Half, Second Half, Player Spotlight, Defining Moment. Sub-second retrieval from Redis cache after first generation.

### Fan Mode (Agent 4)
"My Team's View" tab on any game your team played. Claude rewrites the recap for your team's fans. Tone adapts dynamically: wins get energy, losses get honest analysis. Cached permanently per user per game.

### Predictions
Pick game winners before tipoff with an optional spread prediction. Auto-scored when ingestion detects a game went final. 100 pts for correct winner, 150 pts for correct with spread within 5.

### Leaderboard
Global ranking by total points. Shows prediction accuracy, current login streak, and badges earned. Your rank widget appears if you're outside the top 50.

### Weekly Roster Builder
Pick up to 8 players per week (NBA or NFL). Players are materialized from box score ingestion and sorted by impact score from play-by-play or player stat rows. Roster locks at week start.

### Personalization Data Loading
`/api/teams` now self-seeds NBA and NFL team rows if the database is empty, returns ESPN/public fallback teams if persistence fails, and the onboarding UI also includes a local fallback list so users never see an empty team picker. `/api/users/me/teams` can create a missing fallback team when it is selected. `/api/rosters/players` repairs older box-score-only ingestions by creating missing `players` records and links them to `player_game_stats`; it also falls back to ESPN public athlete leaderboards when no player rows exist.

Team selection is now optional from the dashboard instead of a forced post-login gate. The onboarding route renders local NBA/NFL fallback teams immediately while ESPN syncs in the background, and it navigates back to the feed instantly while favorite-team writes complete asynchronously. Users can edit teams later from the command center or onboarding route; if no teams are selected, all tabs remain accessible.

### ESPN Public API Keys
ESPN's public endpoints do not require API keys. The relevant sport/league slugs are:

| League | Sport key | League key |
|--------|-----------|------------|
| NBA | `basketball` | `nba` |
| NFL | `football` | `nfl` |

Fallback endpoints used by the app:

```text
NBA teams:    https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams
NFL teams:    https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams
NBA players:  https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete
NFL players:  https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/statistics/byathlete
```

### Gamification

| Action | Points |
|--------|--------|
| Correct prediction | 100 |
| Correct + spread within 5 pts | 150 |
| Daily login | 5 |
| 7-day login streak bonus | 25 |
| First prediction of week | 10 |

Badges: First Pick, Oracle (10 correct), Loyal Fan (7-day streak), Superfan (30-day), Analyst (10 recaps), Clutch (within 5 pts).

---

## Project Structure

```
ReplaysAI/
├── main.py                    # FastAPI app, startup, badge seeding
├── config.py                  # Pydantic settings (reads .env)
├── api/
│   ├── auth.py                # /api/users/* -- profile, favorites, notifications
│   ├── feed.py                # /api/feed, /api/games/{id}/fan-recap
│   ├── games.py               # /api/games -- list, detail, plays, highlights
│   ├── recaps.py              # Standard recap generation and cache
│   ├── predictions.py         # Prediction CRUD and upcoming games
│   ├── fantasy.py             # Weekly roster builder
│   ├── rankings.py            # Standings and player profiles
│   └── leaderboards.py        # Global and personal rank
├── agents/
│   ├── orchestrator.py        # Runs agents 1+2 in parallel, feeds agent 3
│   ├── event_extraction.py    # Agent 1: pure Python analytics
│   ├── cv_classification.py   # Agent 2: Claude Vision on video frames
│   ├── llm_summarization.py   # Agent 3: 4-way task-split recap
│   ├── fan_perspective.py     # Agent 4: fan-perspective rewrite (on-demand)
│   └── prediction_scorer.py   # Scores predictions when game goes final
├── db/
│   ├── models.py              # SQLAlchemy ORM -- all 17 tables
│   └── session.py             # Connection pool (size=10, overflow=20)
├── ingestion/
│   ├── nba_ingester.py        # ESPN NBA -> PostgreSQL (live + backfill)
│   ├── nfl_ingester.py        # ESPN NFL -> PostgreSQL (live + backfill)
│   ├── seed_data.py           # Master CLI for historical backfill
│   └── scheduler.py           # Live refresh loop (60s game hours, 5min otherwise)
├── middleware/
│   └── clerk_auth.py          # Clerk JWT verification + user auto-create
├── video/
│   ├── youtube_search.py      # YouTube Data API v3 search
│   └── frame_extractor.py     # yt-dlp download + OpenCV frame extraction
├── cache/
│   └── redis_client.py        # JSON cache with TTL helpers
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Landing.tsx    # Public marketing page
│       │   ├── Onboarding.tsx # Team picker after signup
│       │   ├── Feed.tsx       # Personalized game feed
│       │   ├── GameDetail.tsx # Recap / Fan Mode / Highlights / Plays tabs
│       │   ├── Predictions.tsx
│       │   ├── Leaderboard.tsx
│       │   ├── RosterBuilder.tsx
│       │   └── Profile.tsx
│       ├── components/
│       │   ├── Navbar.tsx
│       │   ├── ProtectedRoute.tsx
│       │   ├── ScoreCard.tsx
│       │   ├── RecapViewer.tsx
│       │   ├── HighlightReel.tsx
│       │   └── PlayTimeline.tsx
│       └── hooks/
│           ├── useGames.ts
│           ├── useUser.ts
│           ├── usePredictions.ts
│           └── useLiveScores.ts
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 16
- Redis 7
- Anthropic API key (for AI recap and CV generation)
- Clerk account (for authentication)

### 1. Clone

```bash
git clone https://github.com/aravinds-kannappan/ReplaysAI.git
cd ReplaysAI
```

### 2. Set up PostgreSQL and Redis

macOS via Homebrew:
```bash
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis
createdb replaysai
```

Docker:
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
# Fill in your keys (see Environment Variables section)
```

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Seed historical data

```bash
# Full backfill: all sports, last 10 seasons (long-running)
python -m ingestion.seed_data

# NBA only, 2 seasons, metadata only (fast, no play-by-play)
python -m ingestion.seed_data --sport nba --seasons 2 --metadata-only

# NFL only
python -m ingestion.seed_data --sport nfl --seasons 10
```

Start the live refresh scheduler after backfill:
```bash
python -m ingestion.scheduler
```

### 5. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:
```
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

```bash
npm run dev
# http://localhost:5173
```

---

## Vercel Deployment Notes

This repository contains both a Vite frontend and a FastAPI backend. The included
`vercel.json` builds `frontend/` and routes `/api/*` requests to the FastAPI app
through `api/index.py`.

Set these environment variables in Vercel before deploying:

Backend:
- `DATABASE_URL` — hosted PostgreSQL connection string. Vercel cannot use the
  local `localhost` Postgres default.
- `REDIS_URL` — hosted Redis connection string.
- `CLERK_SECRET_KEY` — Clerk backend secret for JWT verification.
- `ANTHROPIC_API_KEY` — required for recap/CV/fan-perspective generation.
- `YOUTUBE_API_KEY` — optional but recommended for highlight video discovery.
- `ALLOWED_ORIGINS` — comma-separated frontend origins, for example
  `https://your-app.vercel.app,http://localhost:5173`.

Frontend:
- `VITE_CLERK_PUBLISHABLE_KEY` — Clerk publishable key.
- `VITE_API_BASE_URL` — leave empty when using the same Vercel deployment for
  frontend and backend. Set this only if the API is deployed on another host.

The sports data is real ESPN data, but the app will show empty lists until the
database has been seeded. Run the backfill against your hosted database:

```bash
DATABASE_URL="postgresql://..." REDIS_URL="redis://..." python -m ingestion.seed_data --sport nba --seasons 1
```

Then run `python -m ingestion.scheduler` from a long-running worker environment
for live refreshes. Vercel serverless functions are not a good place for the
continuous scheduler loop.

---

## Environment Variables

Backend (`.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For AI features | Claude Sonnet API key |
| `CLERK_SECRET_KEY` | For auth | Clerk backend secret |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `YOUTUBE_API_KEY` | Optional | YouTube Data API v3 key |
| `ALLOWED_ORIGINS` | Yes in production | Comma-separated allowed frontend origins |

Frontend (`frontend/.env.local`):

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key |
| `VITE_API_BASE_URL` | Optional | API origin if backend is deployed separately |

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

### Auth-required (Authorization: Bearer clerk_jwt)

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

## Data Ingestion

### Historical backfill

`seed_data.py` is the entry point for populating the database with historical data. It iterates every date across the requested seasons, upserts game metadata, then fetches play-by-play and box scores for completed games. The process is idempotent — safe to interrupt and re-run.

```bash
python -m ingestion.seed_data --help

options:
  --sport {nba,nfl,all}   Sport to backfill (default: all)
  --seasons N             Number of past seasons (default: 10)
  --metadata-only         Skip play-by-play and box scores
  --no-boxscores          Skip player stat rows
```

Approximate run times (with play-by-play and box scores):
- NBA 10 seasons: 90-180 min (rate-limited to ~0.45s per request)
- NFL 10 seasons: 40-80 min

### Live refresh

```bash
python -m ingestion.scheduler
```

Polls every 60 seconds during game hours (roughly 2pm-1am UTC), 5 minutes otherwise. Only refreshes recent games — does not re-fetch historical data.

### Running individual ingesters

```bash
python -m ingestion.nba_ingester --mode backfill --seasons 2
python -m ingestion.nba_ingester --mode live

python -m ingestion.nfl_ingester --mode backfill --seasons 3
python -m ingestion.nfl_ingester --mode live
```

---

## CV Pipeline

1. Video discovery: searches YouTube for "{team1} vs {team2} {date} highlights {sport}"
2. Download: yt-dlp at max 480p MP4, audio stripped
3. Frame extraction: OpenCV at 1 frame per 3 seconds, max 60 frames
4. Batch inference: 5 frames per Claude Vision API call
5. Classification: 14 types -- dunk, three_pointer, block, steal, turnover, free_throw, assist, touchdown, interception, field_goal, sack, crowd_reaction, replay, other
6. Storage: frame_timestamp and confidence score stored per frame in cv_classifications

---

## Caching

| Data | Cache key | TTL |
|------|-----------|-----|
| Standard recaps | recap:{game_id} | Permanent |
| Fan recaps | fan_recap:{user_id}:{game_id} | Permanent |
| Standings | rankings:{sport} | 5 minutes |

---

## Roadmap

- Server-Sent Events for live in-game score updates
- Private prediction leagues between friends
- Player stat pages with season trends
- Push notifications for prediction results and highlight alerts
- Additional sports: WNBA, college football, soccer
- Social feed: comment on recaps, react to highlights
