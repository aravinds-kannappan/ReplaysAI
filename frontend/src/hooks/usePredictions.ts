import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/clerk-react";
import axios from "axios";
import { apiPath } from "../lib/api";

async function authFetch(getToken: () => Promise<string | null>, url: string, options: Record<string, unknown> = {}) {
  const token = await getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await axios({ url: apiPath(url), headers, ...options });
  return res.data;
}

export function usePredictions(status?: string) {
  const { getToken } = useAuth();
  return useQuery({
    queryKey: ["predictions", status],
    queryFn: () => authFetch(getToken, "/api/predictions", { params: status ? { status } : {} }),
  });
}

export function useUpcomingGames() {
  const { getToken } = useAuth();
  return useQuery({
    queryKey: ["predictions-upcoming"],
    queryFn: () => authFetch(getToken, "/api/predictions/upcoming"),
    refetchInterval: 60_000,
  });
}

export function useCreatePrediction() {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { game_id: number; predicted_winner_team_id: number; predicted_score_diff?: number }) =>
      authFetch(getToken, "/api/predictions", { method: "post", data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["predictions"] });
      qc.invalidateQueries({ queryKey: ["predictions-upcoming"] });
    },
  });
}

export function useFeed() {
  const { getToken } = useAuth();
  return useQuery({
    queryKey: ["feed"],
    queryFn: () => authFetch(getToken, "/api/feed"),
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
  const { getToken } = useAuth();
  return useQuery({
    queryKey: ["rosters"],
    queryFn: () => authFetch(getToken, "/api/rosters"),
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
    mutationFn: (data: { sport: string; player_ids: number[] }) =>
      authFetch(getToken, "/api/rosters", { method: "post", data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rosters"] }),
  });
}
