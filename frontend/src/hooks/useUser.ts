import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export type FavoriteTeam = {
  id: number;
  external_id?: string;
  abbreviation: string;
  name: string;
  sport: string;
};

export type FollowedPlayer = {
  id: number;
  name: string;
  position?: string | null;
  team?: string | null;
  team_name?: string | null;
  sport: string;
  headshot?: string | null;
};

const TEAMS_KEY = "replaysai:teams";
const PLAYERS_KEY = "replaysai:players";

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

export function setLocalFavoriteTeams(teams: FavoriteTeam[]) {
  if (typeof window === "undefined") return;
  const unique = new Map<string, FavoriteTeam>();
  teams.forEach((team) => unique.set(teamKey(team), team));
  const next = [...unique.values()];
  window.localStorage.setItem(TEAMS_KEY, JSON.stringify(next));
  window.localStorage.setItem("replaysai:onboarded", next.length ? "true" : "false");
}

export function getLocalFollowedPlayers(): FollowedPlayer[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PLAYERS_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    const unique = new Map<number, FollowedPlayer>();
    parsed.forEach((player) => {
      if (player?.id && player?.name) unique.set(player.id, player);
    });
    return [...unique.values()];
  } catch {
    return [];
  }
}

export function setLocalFollowedPlayers(players: FollowedPlayer[]) {
  if (typeof window === "undefined") return;
  const unique = new Map<number, FollowedPlayer>();
  players.forEach((player) => unique.set(player.id, player));
  window.localStorage.setItem(PLAYERS_KEY, JSON.stringify([...unique.values()]));
}

export function useCurrentUser() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const localTeams = getLocalFavoriteTeams();
      const localPlayers = getLocalFollowedPlayers();
      const displayName =
        (typeof window !== "undefined" && window.localStorage.getItem("replaysai:name")) || null;
      return {
        id: "local",
        username: null,
        display_name: displayName,
        email: null,
        avatar_url: null,
        bio: null,
        total_points: 0,
        login_streak: 0,
        prediction_accuracy: 0,
        badges: [],
        favorite_teams: localTeams,
        followed_players: localPlayers,
        onboarded: localTeams.length > 0,
      };
    },
    enabled: true,
    staleTime: 10_000,
  });
}

export function useAddFavoriteTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (team: FavoriteTeam) => {
      setLocalFavoriteTeams([...getLocalFavoriteTeams(), team]);
      return { status: "ok" };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["feed"] });
    },
  });
}

export function useRemoveFavoriteTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (team: Pick<FavoriteTeam, "id" | "sport" | "abbreviation">) => {
      setLocalFavoriteTeams(getLocalFavoriteTeams().filter((item) => teamKey(item) !== teamKey(team)));
      return { status: "ok" };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["feed"] });
    },
  });
}

export function useToggleFollowedPlayer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (player: FollowedPlayer) => {
      const current = getLocalFollowedPlayers();
      const exists = current.some((item) => item.id === player.id);
      setLocalFollowedPlayers(
        exists ? current.filter((item) => item.id !== player.id) : [...current, player],
      );
      return { following: !exists };
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
