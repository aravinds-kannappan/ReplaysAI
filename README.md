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
| Backend | Python 3.10+, FastAPI, asyncio |
| Optional ingestion storage | PostgreSQL 16 for offline backfills only |
| Cache | Redis 7 optional |
| AI | OpenAI or Anthropic for chatbot/recap text |
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
| AI | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | Dynamic chatbot replies and generated analysis |

Recommended:

| Service | Env var | Why |
|---------|---------|-----|
| Redis | `REDIS_URL` | Cache ESPN-derived standings, recaps, and repeated agent outputs |
| YouTube Data API | `YOUTUBE_API_KEY` | Better highlight/video discovery for reels |

Not required:

| Service | Key needed? | Notes |
|---------|-------------|-------|
| ESPN public data | No | NBA/NFL teams, athletes, scoreboards, summaries, and play labels use public ESPN endpoints with sport/league slugs. |

If `ANTHROPIC_API_KEY` is not set, `/api/chat` returns a setup message instead of pretending to be intelligent.
`OPENAI_API_KEY` is also supported and is checked first.

---

## Architecture

### Multi-Agent Inference Pipeline

Three agents run in parallel via `asyncio.gather()`. The most expensive steps — CV inference and LLM generation — run concurrently to minimize latency.

```
ESPN API
    |
    v
FastAPI routes  <--  ESPN teams, games, plays, athletes
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

### Optional Database Models

The API no longer needs a database for Vercel. The `db/` models remain for optional offline ingestion/backfill work only.

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
Pick game winners before tipoff with an optional spread prediction. Picks are stored immediately in browser state when running without a database.

### Leaderboard
The leaderboard endpoints stay available, but global scoring requires adding a durable store later. Without a database, user picks and rosters are local to the browser.

### Weekly Roster Builder
Pick up to 8 players per week (NBA or NFL). Player pools come from ESPN public athlete leaderboards and saved rosters are local when no database is configured.

### Personalization Data Loading
`/api/teams` reads NBA and NFL team rows directly from ESPN public endpoints. `/api/rosters/players` reads real ESPN public athlete leaderboards.

Team selection is optional from the dashboard instead of a forced post-login gate. The onboarding route renders ESPN teams only; if ESPN is unavailable, it shows an empty source state rather than fake teams. Users can edit teams later from the command center or onboarding route; if no teams are selected, all tabs remain accessible.

### ESPN Public API Keys
ESPN's public endpoints do not require API keys. The relevant sport/league slugs are:

| League | Sport key | League key |
|--------|-----------|------------|
| NBA | `basketball` | `nba` |
| NFL | `football` | `nfl` |

Public endpoints used by the app:

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
- Redis 7 optional
- OpenAI or Anthropic API key optional for LLM replies
- Clerk account (for authentication)

### 1. Clone

```bash
git clone https://github.com/aravinds-kannappan/ReplaysAI.git
cd ReplaysAI
```

### 2. Optional Redis

The Vercel app runs without PostgreSQL. Redis is optional for cache speed.

macOS via Homebrew:
```bash
brew install redis
brew services start redis
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
- `CLERK_SECRET_KEY` — Clerk backend secret for JWT verification.
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` — optional, but required for true LLM chatbot responses.
- `OPENAI_MODEL` or `ANTHROPIC_MODEL` — optional model overrides.
- `REDIS_URL` — optional hosted Redis connection string.
- `YOUTUBE_API_KEY` — optional but recommended for highlight video discovery.
- `ALLOWED_ORIGINS` — comma-separated frontend origins, for example
  `https://your-app.vercel.app,http://localhost:5173`.

Frontend:
- `VITE_CLERK_PUBLISHABLE_KEY` — Clerk publishable key.
- `VITE_API_BASE_URL` — leave empty when using the same Vercel deployment for
  frontend and backend. Set this only if the API is deployed on another host.

The deployed app does not require a database URL. NBA/NFL teams, schedules,
plays, recaps, roster players, and reel cut manifests are derived from real ESPN
public endpoints at request time. If you later add durable global scoring or
offline backfills, run those from a worker environment rather than Vercel
serverless functions.

---

## Environment Variables

Backend (`.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `CLERK_SECRET_KEY` | For auth | Clerk backend secret |
| `OPENAI_API_KEY` | For AI features | OpenAI API key |
| `OPENAI_MODEL` | Optional | Defaults to `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | For AI features | Anthropic API key if OpenAI is not set |
| `ANTHROPIC_MODEL` | Optional | Defaults to `claude-3-5-sonnet-latest` |
| `REDIS_URL` | Optional | Redis connection string |
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

`seed_data.py` is an optional entry point for populating a PostgreSQL database with historical data if you later decide to run durable offline backfills. The Vercel app does not require this. The script iterates every date across the requested seasons, upserts game metadata, then fetches play-by-play and box scores for completed games.

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
