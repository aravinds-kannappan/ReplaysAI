import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth, useUser as useClerkUser } from "@clerk/clerk-react";
import axios from "axios";
import { apiPath } from "../lib/api";

export type FavoriteTeam = {
  id: number;
  external_id?: string;
  abbreviation: string;
  name: string;
  sport: string;
};

const TEAMS_KEY = "replaysai:teams";

function teamKey(team: Pick<FavoriteTeam, "sport" | "abbreviation">) {
  return `${team.sport}:${team.abbreviation}`;
}

export function getLocalFavoriteTeams(): FavoriteTeam[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(TEAMS_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    const unique = new Map<string, FavoriteTeam>();
    parsed.forEach((team) => {
      if (team?.sport && team?.abbreviation && team?.name) {
        unique.set(teamKey(team), team);
      }
    });
    return [...unique.values()];
  } catch {
    return [];
  }
}

function setLocalFavoriteTeams(teams: FavoriteTeam[]) {
  if (typeof window === "undefined") return;
  const unique = new Map<string, FavoriteTeam>();
  teams.forEach((team) => unique.set(teamKey(team), team));
  const next = [...unique.values()];
  window.localStorage.setItem(TEAMS_KEY, JSON.stringify(next));
  window.localStorage.setItem("replaysai:onboarded", next.length ? "true" : "false");
}

async function authFetch(getToken: () => Promise<string | null>, url: string, options: Record<string, unknown> = {}) {
  const token = await getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await axios({ url: apiPath(url), headers, ...options });
  return res.data;
}

export function useCurrentUser() {
  const { getToken, isSignedIn } = useAuth();
  const { user: clerkUser } = useClerkUser();
  return useQuery({
    queryKey: ["me", clerkUser?.id],
    queryFn: async () => {
      const localTeams = getLocalFavoriteTeams();
      let apiUser: Record<string, unknown> = {};
      if (isSignedIn) {
        try {
          apiUser = await authFetch(getToken, "/api/users/me");
        } catch {
          apiUser = {};
        }
      }
      return {
        id: clerkUser?.id ?? "local",
        username: clerkUser?.username ?? null,
        display_name: clerkUser?.fullName ?? clerkUser?.firstName ?? null,
        email: clerkUser?.primaryEmailAddress?.emailAddress ?? null,
        avatar_url: clerkUser?.imageUrl ?? null,
        bio: null,
        total_points: 0,
        login_streak: 0,
        prediction_accuracy: 0,
        badges: [],
        ...apiUser,
        favorite_teams: localTeams,
        onboarded: localTeams.length > 0,
      };
    },
    enabled: true,
    staleTime: 10_000,
  });
}

export function useAddFavoriteTeam() {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (team: FavoriteTeam) => {
      setLocalFavoriteTeams([...getLocalFavoriteTeams(), team]);
      try {
        await authFetch(getToken, "/api/users/me/teams", {
          method: "post",
          data: { team_id: team.id, sport: team.sport },
        });
      } catch {
        // Local browser state is the source of truth when no database is configured.
      }
      return { status: "ok" };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["feed"] });
    },
  });
}

export function useRemoveFavoriteTeam() {
  const { getToken } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (team: Pick<FavoriteTeam, "id" | "sport" | "abbreviation">) => {
      setLocalFavoriteTeams(getLocalFavoriteTeams().filter((item) => teamKey(item) !== teamKey(team)));
      try {
        await authFetch(getToken, `/api/users/me/teams/${team.id}`, { method: "delete" });
      } catch {
        // Local browser state is the source of truth when no database is configured.
      }
      return { status: "ok" };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["feed"] });
    },
  });
}

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => [],
    refetchInterval: 60_000,
  });
}
