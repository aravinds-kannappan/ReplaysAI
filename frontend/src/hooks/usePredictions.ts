import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/clerk-react";
import axios from "axios";
import { apiPath } from "../lib/api";
import { getLocalFavoriteTeams } from "./useUser";

const PREDICTIONS_KEY = "replaysai:predictions";
const ROSTERS_KEY = "replaysai:rosters";

function readLocal<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    return JSON.parse(window.localStorage.getItem(key) || "") || fallback;
  } catch {
    return fallback;
  }
}

function writeLocal<T>(key: string, value: T) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(key, JSON.stringify(value));
  }
}

async function authFetch(getToken: () => Promise<string | null>, url: string, options: Record<string, unknown> = {}) {
  const token = await getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await axios({ url: apiPath(url), headers, ...options });
  return res.data;
}

export function usePredictions(status?: string) {
  return useQuery({
    queryKey: ["predictions", status],
    queryFn: () => {
      const predictions = readLocal<Record<string, unknown>[]>(PREDICTIONS_KEY, []);
      if (status === "resolved") return predictions.filter((prediction) => prediction.resolved_at);
      if (status === "pending") return predictions.filter((prediction) => !prediction.resolved_at);
      return predictions;
    },
  });
}

export function useUpcomingGames() {
  const { getToken } = useAuth();
  return useQuery({
    queryKey: ["predictions-upcoming"],
    queryFn: async () => {
      const games = await authFetch(getToken, "/api/predictions/upcoming");
      const predicted = new Set(readLocal<{ game_id: number }[]>(PREDICTIONS_KEY, []).map((item) => item.game_id));
      return games.map((game: { id: number }) => ({ ...game, already_predicted: predicted.has(game.id) }));
    },
    refetchInterval: 60_000,
  });
}

export function useCreatePrediction() {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: { game_id: number; predicted_winner_team_id: number; predicted_score_diff?: number }) => {
      const predictions = readLocal<Record<string, unknown>[]>(PREDICTIONS_KEY, []);
      const next = [
        ...predictions.filter((prediction) => prediction.game_id !== data.game_id),
        { id: data.game_id, ...data, created_at: new Date().toISOString(), is_correct: null, points_earned: 0 },
      ];
      writeLocal(PREDICTIONS_KEY, next);
      try {
        await authFetch(getToken, "/api/predictions", { method: "post", data });
      } catch {
        // Picks are intentionally local when no database is configured.
      }
      return next[next.length - 1];
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["predictions"] });
      qc.invalidateQueries({ queryKey: ["predictions-upcoming"] });
    },
  });
}

export function useFeed() {
  const { getToken } = useAuth();
  const favoriteTeams = getLocalFavoriteTeams();
  const favoriteKeys = favoriteTeams.map((team) => `${team.sport}:${team.abbreviation}`).join(",");
  return useQuery({
    queryKey: ["feed", favoriteKeys],
    queryFn: () => authFetch(getToken, "/api/feed", { params: favoriteKeys ? { favorite_teams: favoriteKeys } : {} }),
    refetchInterval: 30_000,
  });
}

export function useLeaderboard() {
  const { getToken } = useAuth();
  return useQuery({
    queryKey: ["leaderboard"],
    queryFn: () => authFetch(getToken, "/api/leaderboard"),
    staleTime: 120_000,
  });
}

export function useMyRank() {
  const { getToken } = useAuth();
  return useQuery({
    queryKey: ["leaderboard-me"],
    queryFn: () => authFetch(getToken, "/api/leaderboard/me"),
  });
}

export function useRosters() {
  return useQuery({
    queryKey: ["rosters"],
    queryFn: () => readLocal<Record<string, unknown>[]>(ROSTERS_KEY, []),
  });
}

export function useRosterPlayers(sport?: string) {
  const { getToken } = useAuth();
  return useQuery({
    queryKey: ["roster-players", sport],
    queryFn: () => authFetch(getToken, "/api/rosters/players", { params: sport ? { sport } : {} }),
  });
}

export function useSaveRoster() {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: { sport: string; player_ids: number[] }) => {
      const rosters = readLocal<Record<string, unknown>[]>(ROSTERS_KEY, []);
      const weekLabel = `${new Date().getFullYear()}-local`;
      const nextRoster = {
        id: `${data.sport}:${weekLabel}`,
        sport: data.sport,
        week_label: weekLabel,
        player_ids: data.player_ids,
        total_points: 0,
        locked: false,
      };
      writeLocal(ROSTERS_KEY, [...rosters.filter((roster) => roster.sport !== data.sport), nextRoster]);
      try {
        await authFetch(getToken, "/api/rosters", { method: "post", data });
      } catch {
        // Lineups are intentionally local when no database is configured.
      }
      return nextRoster;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rosters"] }),
  });
}
