import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// ── Anonymous identity ─────────────────────────────────────────────────────────
// A UUID is generated once per browser and stored in localStorage. On first use
// it is upserted into the Supabase users table so social features (leaderboard,
// reactions, newsletter) have a stable key to write to.

const USER_ID_KEY = "replaysai:uid";

export function getOrCreateUserId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

export async function ensureUserRow(displayName?: string): Promise<void> {
  const id = getOrCreateUserId();
  if (!id) return;
  const { error } = await supabase
    .from("users")
    .upsert({ id, display_name: displayName ?? null }, { onConflict: "id", ignoreDuplicates: true });
  if (error) console.warn("[supabase] ensureUserRow:", error.message);
}

// ── Predictions (Supabase-backed) ─────────────────────────────────────────────
export type DbPrediction = {
  id: string;
  user_id: string;
  game_id: number;
  sport: string;
  predicted_team_id: number | null;
  predicted_team_abbr: string | null;
  result: string | null;
  points_earned: number;
  created_at: string;
};

export async function upsertPrediction(pred: Omit<DbPrediction, "id" | "created_at" | "result" | "points_earned">): Promise<void> {
  const { error } = await supabase
    .from("predictions")
    .upsert(pred, { onConflict: "user_id,game_id" });
  if (error) console.warn("[supabase] upsertPrediction:", error.message);
}

export async function fetchPredictions(userId: string): Promise<DbPrediction[]> {
  const { data, error } = await supabase
    .from("predictions")
    .select("*")
    .eq("user_id", userId)
    .order("created_at", { ascending: false });
  if (error) console.warn("[supabase] fetchPredictions:", error.message);
  return (data ?? []) as DbPrediction[];
}

// ── Leaderboard ───────────────────────────────────────────────────────────────
export type LeaderboardRow = {
  user_id: string;
  sport: string;
  total_points: number;
  correct_picks: number;
  total_picks: number;
  current_streak: number;
  best_streak: number;
  display_name?: string | null;
};

export async function fetchLeaderboard(sport: string, limit = 20): Promise<LeaderboardRow[]> {
  const { data, error } = await supabase
    .from("leaderboard")
    .select("user_id, sport, total_points, correct_picks, total_picks, current_streak, best_streak, users(display_name)")
    .eq("sport", sport)
    .order("total_points", { ascending: false })
    .limit(limit);
  if (error) console.warn("[supabase] fetchLeaderboard:", error.message);
  return ((data ?? []) as unknown as (LeaderboardRow & { users: { display_name: string | null } | null })[]).map((r) => ({
    ...r,
    display_name: r.users?.display_name ?? null,
  }));
}

// ── Newsletter ────────────────────────────────────────────────────────────────
export type Newsletter = {
  id: string;
  user_id: string;
  week_key: string;
  content_md: string;
  teams_snapshot: unknown;
  share_token: string;
  created_at: string;
};

export async function fetchNewsletter(userId: string, weekKey: string): Promise<Newsletter | null> {
  const { data, error } = await supabase
    .from("newsletters")
    .select("*")
    .eq("user_id", userId)
    .eq("week_key", weekKey)
    .maybeSingle();
  if (error) console.warn("[supabase] fetchNewsletter:", error.message);
  return (data as Newsletter | null);
}

export async function fetchNewsletterByToken(token: string): Promise<Newsletter | null> {
  const { data, error } = await supabase
    .from("newsletters")
    .select("*")
    .eq("share_token", token)
    .maybeSingle();
  if (error) console.warn("[supabase] fetchNewsletterByToken:", error.message);
  return (data as Newsletter | null);
}

export async function saveNewsletter(row: Omit<Newsletter, "id" | "created_at" | "share_token">): Promise<Newsletter | null> {
  const { data, error } = await supabase
    .from("newsletters")
    .upsert(row, { onConflict: "user_id,week_key" })
    .select()
    .maybeSingle();
  if (error) console.warn("[supabase] saveNewsletter:", error.message);
  return (data as Newsletter | null);
}

// ── Reactions ─────────────────────────────────────────────────────────────────
export async function upsertReaction(userId: string, gameId: number, reaction: "fire" | "cold" | "mind-blown"): Promise<void> {
  const { error } = await supabase
    .from("reel_reactions")
    .upsert({ user_id: userId, game_id: gameId, reaction }, { onConflict: "user_id,game_id" });
  if (error) console.warn("[supabase] upsertReaction:", error.message);
}

export async function fetchReactionCounts(gameId: number): Promise<Record<string, number>> {
  const { data, error } = await supabase
    .from("reel_reactions")
    .select("reaction")
    .eq("game_id", gameId);
  if (error) return {};
  const counts: Record<string, number> = { fire: 0, cold: 0, "mind-blown": 0 };
  (data ?? []).forEach((r: { reaction: string }) => { counts[r.reaction] = (counts[r.reaction] ?? 0) + 1; });
  return counts;
}
