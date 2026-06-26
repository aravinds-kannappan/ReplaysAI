import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

// Supabase is OPTIONAL. It powers cross-device persistence and shareable links,
// but the app is fully usable without it: newsletters render from the freshly
// generated payload and fall back to localStorage, predictions stay local, etc.
// Creating the client with undefined env vars throws, so guard it — otherwise a
// missing key would crash every page that imports this module.
export const supabase: SupabaseClient | null =
  supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;
export const supabaseEnabled = supabase !== null;

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
  if (!supabase) return;
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
  if (!supabase) return;
  const { error } = await supabase
    .from("predictions")
    .upsert(pred, { onConflict: "user_id,game_id" });
  if (error) console.warn("[supabase] upsertPrediction:", error.message);
}

export async function fetchPredictions(userId: string): Promise<DbPrediction[]> {
  if (!supabase) return [];
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
  if (!supabase) return [];
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

// Local cache so newsletters survive reloads even without Supabase. Keyed per
// user+week so editing teams and regenerating works as expected.
function localNewsletterKey(userId: string, weekKey: string) {
  return `replaysai:newsletter:${userId}:${weekKey}`;
}

export function readLocalNewsletter(userId: string, weekKey: string): Newsletter | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(localNewsletterKey(userId, weekKey));
    return raw ? (JSON.parse(raw) as Newsletter) : null;
  } catch {
    return null;
  }
}

export function writeLocalNewsletter(n: Newsletter): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(localNewsletterKey(n.user_id, n.week_key), JSON.stringify(n));
  } catch {
    /* storage full / unavailable — non-fatal */
  }
}

export async function fetchNewsletter(userId: string, weekKey: string): Promise<Newsletter | null> {
  if (!supabase) return readLocalNewsletter(userId, weekKey);
  const { data, error } = await supabase
    .from("newsletters")
    .select("*")
    .eq("user_id", userId)
    .eq("week_key", weekKey)
    .maybeSingle();
  if (error) console.warn("[supabase] fetchNewsletter:", error.message);
  return (data as Newsletter | null) ?? readLocalNewsletter(userId, weekKey);
}

export async function fetchNewsletterByToken(token: string): Promise<Newsletter | null> {
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("newsletters")
    .select("*")
    .eq("share_token", token)
    .maybeSingle();
  if (error) console.warn("[supabase] fetchNewsletterByToken:", error.message);
  return (data as Newsletter | null);
}

export async function saveNewsletter(row: Omit<Newsletter, "id" | "created_at" | "share_token">): Promise<Newsletter | null> {
  // Always keep a local copy so the digest renders even if the remote write
  // fails (tables missing, RLS, offline). Supabase only adds shareable links.
  const local: Newsletter = {
    id: `${row.user_id}:${row.week_key}`,
    share_token: "",
    created_at: new Date().toISOString(),
    ...row,
  };
  writeLocalNewsletter(local);
  if (!supabase) return local;
  const { data, error } = await supabase
    .from("newsletters")
    .upsert(row, { onConflict: "user_id,week_key" })
    .select()
    .maybeSingle();
  if (error) {
    console.warn("[supabase] saveNewsletter:", error.message);
    return local;
  }
  const saved = (data as Newsletter | null) ?? local;
  writeLocalNewsletter(saved);
  return saved;
}

// ── Reactions ─────────────────────────────────────────────────────────────────
export async function upsertReaction(userId: string, gameId: number, reaction: "fire" | "cold" | "mind-blown"): Promise<void> {
  if (!supabase) return;
  const { error } = await supabase
    .from("reel_reactions")
    .upsert({ user_id: userId, game_id: gameId, reaction }, { onConflict: "user_id,game_id" });
  if (error) console.warn("[supabase] upsertReaction:", error.message);
}

export async function fetchReactionCounts(gameId: number): Promise<Record<string, number>> {
  if (!supabase) return {};
  const { data, error } = await supabase
    .from("reel_reactions")
    .select("reaction")
    .eq("game_id", gameId);
  if (error) return {};
  const counts: Record<string, number> = { fire: 0, cold: 0, "mind-blown": 0 };
  (data ?? []).forEach((r: { reaction: string }) => { counts[r.reaction] = (counts[r.reaction] ?? 0) + 1; });
  return counts;
}
