/*
# ReplaysAI Core Tables

## Overview
Creates the persistence layer for ReplaysAI: anonymous user identities, predictions,
leaderboard tracking, personalized newsletters, and reel reactions.

## New Tables

### users
Stores anonymous fan identities created client-side. A UUID is generated in the
browser on first visit and upserted here. No auth.users dependency — this is
a lightweight identity anchor for social features.
- id (uuid, primary key) — generated client-side
- display_name (text) — optional fan handle
- created_at (timestamptz)

### predictions
One row per pick. Locked when created; result/points filled in after the game ends.
- id (uuid, primary key)
- user_id (uuid, FK → users.id)
- game_id (bigint) — ESPN game ID
- sport (text) — NBA or NFL
- predicted_team_id (bigint) — ESPN team ID
- predicted_team_abbr (text)
- result (text nullable) — 'correct' | 'incorrect', null until scored
- points_earned (int default 0)
- created_at (timestamptz)

### leaderboard
One row per user per sport. Upserted whenever predictions are scored.
- user_id (uuid, FK → users.id)
- sport (text)
- total_points (int default 0)
- correct_picks (int default 0)
- total_picks (int default 0)
- current_streak (int default 0)
- best_streak (int default 0)
- updated_at (timestamptz)
- PRIMARY KEY (user_id, sport)

### newsletters
One row per user per week. Content is cached — Claude is only called once per
user per week. Share token enables public read of a single newsletter.
- id (uuid, primary key)
- user_id (uuid, FK → users.id)
- week_key (text) — ISO year-week e.g. "2026-W26"
- content_md (text) — Markdown newsletter body
- teams_snapshot (jsonb) — team abbreviations at generation time
- share_token (text unique) — random hex for public sharing
- created_at (timestamptz)

### reel_reactions
Emoji reactions on reels/games. One reaction per user per game.
- id (uuid, primary key)
- user_id (uuid, FK → users.id)
- game_id (bigint)
- reaction (text) — 'fire' | 'cold' | 'mind-blown'
- created_at (timestamptz)

## Security
All tables use RLS. This app has no login screen so all policies grant access to
both anon and authenticated roles. Ownership is enforced by user_id (a UUID the
client generates and stores in localStorage — not auth.uid()).

## Important Notes
1. No auth.users foreign key — users.id is a client-generated UUID.
2. Leaderboard uses composite primary key (user_id, sport) for upsert.
3. share_token on newsletters is UNIQUE so a guessed token hits exactly one row.
4. reel_reactions is insert-only from the client; no update needed.
*/

-- ── users ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY,
  display_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_users" ON users;
CREATE POLICY "anon_select_users" ON users FOR SELECT
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_users" ON users;
CREATE POLICY "anon_insert_users" ON users FOR INSERT
  TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_users" ON users;
CREATE POLICY "anon_update_users" ON users FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);

-- ── predictions ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  game_id bigint NOT NULL,
  sport text NOT NULL,
  predicted_team_id bigint,
  predicted_team_abbr text,
  result text,
  points_earned int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS predictions_user_id_idx ON predictions(user_id);
CREATE INDEX IF NOT EXISTS predictions_game_id_idx ON predictions(game_id);

ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_predictions" ON predictions;
CREATE POLICY "anon_select_predictions" ON predictions FOR SELECT
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_predictions" ON predictions;
CREATE POLICY "anon_insert_predictions" ON predictions FOR INSERT
  TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_predictions" ON predictions;
CREATE POLICY "anon_update_predictions" ON predictions FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);

-- ── leaderboard ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leaderboard (
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  sport text NOT NULL,
  total_points int NOT NULL DEFAULT 0,
  correct_picks int NOT NULL DEFAULT 0,
  total_picks int NOT NULL DEFAULT 0,
  current_streak int NOT NULL DEFAULT 0,
  best_streak int NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, sport)
);

CREATE INDEX IF NOT EXISTS leaderboard_sport_points_idx ON leaderboard(sport, total_points DESC);

ALTER TABLE leaderboard ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_leaderboard" ON leaderboard;
CREATE POLICY "anon_select_leaderboard" ON leaderboard FOR SELECT
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_leaderboard" ON leaderboard;
CREATE POLICY "anon_insert_leaderboard" ON leaderboard FOR INSERT
  TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_leaderboard" ON leaderboard;
CREATE POLICY "anon_update_leaderboard" ON leaderboard FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);

-- ── newsletters ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS newsletters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  week_key text NOT NULL,
  content_md text NOT NULL,
  teams_snapshot jsonb,
  share_token text UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(16), 'hex'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, week_key)
);

CREATE INDEX IF NOT EXISTS newsletters_share_token_idx ON newsletters(share_token);

ALTER TABLE newsletters ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_newsletters" ON newsletters;
CREATE POLICY "anon_select_newsletters" ON newsletters FOR SELECT
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_newsletters" ON newsletters;
CREATE POLICY "anon_insert_newsletters" ON newsletters FOR INSERT
  TO anon, authenticated WITH CHECK (true);

-- ── reel_reactions ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reel_reactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  game_id bigint NOT NULL,
  reaction text NOT NULL CHECK (reaction IN ('fire', 'cold', 'mind-blown')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, game_id)
);

CREATE INDEX IF NOT EXISTS reel_reactions_game_id_idx ON reel_reactions(game_id);

ALTER TABLE reel_reactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_reel_reactions" ON reel_reactions;
CREATE POLICY "anon_select_reel_reactions" ON reel_reactions FOR SELECT
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_reel_reactions" ON reel_reactions;
CREATE POLICY "anon_insert_reel_reactions" ON reel_reactions FOR INSERT
  TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_reel_reactions" ON reel_reactions;
CREATE POLICY "anon_update_reel_reactions" ON reel_reactions FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
