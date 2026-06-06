import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import type { RankingsResponse } from "../types";
import { apiPath } from "../lib/api";

export function useRankings(sport?: string) {
  return useQuery<RankingsResponse>({
    queryKey: ["rankings", sport],
    queryFn: () => axios.get(apiPath("/api/rankings"), { params: sport ? { sport } : {} }).then((r) => r.data),
    refetchInterval: 300_000,
    staleTime: 60_000,
  });
}
