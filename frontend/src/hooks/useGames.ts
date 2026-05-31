import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import type { GamesResponse, Game, PlaysResponse, Recap, HighlightsResponse } from "../types";

const API = "";

export function useGames(params: { sport?: string; status?: string; date?: string; limit?: number } = {}) {
  return useQuery<GamesResponse>({
    queryKey: ["games", params],
    queryFn: () => axios.get(`${API}/api/games`, { params }).then((r) => r.data),
    refetchInterval: 30_000,
  });
}

export function useGame(id: number) {
  return useQuery<Game>({
    queryKey: ["game", id],
    queryFn: () => axios.get(`${API}/api/games/${id}`).then((r) => r.data),
    refetchInterval: 30_000,
  });
}

export function usePlays(gameId: number, params: { period?: number; play_type?: string; limit?: number } = {}) {
  return useQuery<PlaysResponse>({
    queryKey: ["plays", gameId, params],
    queryFn: () => axios.get(`${API}/api/games/${gameId}/plays`, { params: { limit: 200, ...params } }).then((r) => r.data),
  });
}

export function useRecap(gameId: number) {
  return useQuery<Recap>({
    queryKey: ["recap", gameId],
    queryFn: () => axios.get(`${API}/api/games/${gameId}/recap`).then((r) => r.data),
    retry: false,
  });
}

export function useHighlights(gameId: number) {
  return useQuery<HighlightsResponse>({
    queryKey: ["highlights", gameId],
    queryFn: () => axios.get(`${API}/api/games/${gameId}/highlights`).then((r) => r.data),
  });
}

export async function triggerRecapGeneration(gameId: number) {
  return axios.post(`${API}/api/games/${gameId}/generate`).then((r) => r.data);
}
