import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/clerk-react";
import axios from "axios";

async function authFetch(getToken: () => Promise<string | null>, url: string, options: Record<string, unknown> = {}) {
  const token = await getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await axios({ url, headers, ...options });
  return res.data;
}

export function useCurrentUser() {
  const { getToken, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["me"],
    queryFn: () => authFetch(getToken, "/api/users/me"),
    enabled: !!isSignedIn,
    staleTime: 60_000,
  });
}

export function useAddFavoriteTeam() {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (team_id: number) =>
      authFetch(getToken, "/api/users/me/teams", { method: "post", data: { team_id } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useRemoveFavoriteTeam() {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (team_id: number) =>
      authFetch(getToken, `/api/users/me/teams/${team_id}`, { method: "delete" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useNotifications() {
  const { getToken, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => authFetch(getToken, "/api/users/me/notifications"),
    enabled: !!isSignedIn,
    refetchInterval: 60_000,
  });
}
