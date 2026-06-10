import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { apiPath } from "../lib/api";
import { useCurrentUser, useAddFavoriteTeam } from "../hooks/useUser";

type Team = {
  id: number;
  abbreviation: string;
  name: string;
  sport: string;
};

function teamKey(team: Pick<Team, "sport" | "abbreviation">) {
  return `${team.sport}:${team.abbreviation}`;
}

function TeamSection({
  title,
  emoji,
  teams,
  loading,
  activeKeys,
  favTeamKeys,
  onToggle,
}: {
  title: string;
  emoji: string;
  teams: Team[];
  loading: boolean;
  activeKeys: Set<string>;
  favTeamKeys: Set<string>;
  onToggle: (team: Team) => void;
}) {
  return (
    <div className="team-section">
      <h3>{emoji} {title}</h3>
      {loading ? (
        <p className="loading-text">Syncing live ESPN teams...</p>
      ) : teams.length === 0 ? (
        <p className="empty-state">No teams loaded — the team feed is unreachable. Refresh to retry.</p>
      ) : (
        <div className="team-grid">
          {teams.map((team) => {
            const key = teamKey(team);
            const isSelected = activeKeys.has(key) || favTeamKeys.has(key);
            return (
              <button
                key={key}
                className={`team-chip ${isSelected ? "selected" : ""}`}
                onClick={() => onToggle(team)}
              >
                <span className="chip-abbr">{team.abbreviation}</span>
                <span className="chip-name">{team.name}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Onboarding() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const addTeam = useAddFavoriteTeam();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data: nbaTeams = [], isLoading: nbaLoading } = useQuery<Team[]>({
    queryKey: ["teams", "NBA"],
    queryFn: () => axios.get(apiPath("/api/teams"), { params: { sport: "NBA" } }).then((r) => r.data),
  });

  const { data: nflTeams = [], isLoading: nflLoading } = useQuery<Team[]>({
    queryKey: ["teams", "NFL"],
    queryFn: () => axios.get(apiPath("/api/teams"), { params: { sport: "NFL" } }).then((r) => r.data),
  });

  const favoriteTeams = (user?.favorite_teams ?? []) as { id: number; sport: string; abbreviation: string }[];
  const favTeamKeys = new Set<string>(favoriteTeams.map((t) => `${t.sport}:${t.abbreviation}`));
  const activeKeys = selected.size > 0 ? selected : favTeamKeys;
  const visibleNbaTeams = nbaTeams;
  const visibleNflTeams = nflTeams;

  function toggleTeam(team: Team) {
    setSelected((prev) => {
      const next = new Set(prev);
      favTeamKeys.forEach((key) => next.add(key));
      const key = teamKey(team);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  // Kick the downstream agents the moment teams are confirmed: warm the
  // personalized feed, then build 2/5/10-minute reel cut manifests for the top
  // favorite-team games so Feed and Reels are ready when the user lands there.
  // Query keys must match useFeed (["feed", keys]) and Reels (["reel-cuts", id]).
  async function warmDownstream(teams: Team[]) {
    const favoriteKeys = teams.map((team) => teamKey(team)).join(",");
    try {
      const feed = await queryClient.fetchQuery({
        queryKey: ["feed", favoriteKeys],
        queryFn: () =>
          axios.get(apiPath("/api/feed"), { params: { favorite_teams: favoriteKeys } }).then((r) => r.data),
      });
      const topGames = ((feed?.games ?? []) as { id: number }[]).slice(0, 3);
      await Promise.allSettled(
        topGames.map((game) =>
          queryClient.prefetchQuery({
            queryKey: ["reel-cuts", game.id],
            queryFn: () => axios.get(apiPath(`/api/games/${game.id}/reels`)).then((r) => r.data),
            staleTime: 300_000,
          }),
        ),
      );
    } catch {
      // Warming is best-effort; every tab still fetches on mount.
    }
  }

  function continueToFeed() {
    const teams = [...visibleNbaTeams, ...visibleNflTeams].filter((team) => activeKeys.has(teamKey(team)));
    if (!teams.length) return;
    window.localStorage.setItem("replaysai:onboarded", "true");
    window.localStorage.setItem("replaysai:teams", JSON.stringify(teams));
    teams.forEach((team) => addTeam.mutate(team));
    void warmDownstream(teams);
    navigate("/feed");
  }

  return (
    <div className="onboarding-page">
      <div className="onboarding-header">
        <p className="dashboard-kicker">Personalization survey</p>
        <h1>Who should ReplaysAI follow for you?</h1>
        <p>Select NBA and NFL teams once. Agents use this to retrieve schedules, players, reels, predictions, and fantasy context.</p>
        <div className="onboarding-steps">
          <span className="step active">1. Choose Teams</span>
          <span className="step-arrow">→</span>
          <span className="step">2. Your Feed</span>
        </div>
      </div>

      <TeamSection title="NBA Teams" emoji="🏀" teams={visibleNbaTeams} loading={nbaLoading} activeKeys={activeKeys} favTeamKeys={favTeamKeys} onToggle={toggleTeam} />
      <TeamSection title="NFL Teams" emoji="🏈" teams={visibleNflTeams} loading={nflLoading} activeKeys={activeKeys} favTeamKeys={favTeamKeys} onToggle={toggleTeam} />

      <div className="onboarding-footer">
        <button
          className="btn-hero-primary"
          onClick={continueToFeed}
          disabled={activeKeys.size === 0}
        >
          {activeKeys.size === 0
            ? "Pick at least one team"
            : `Continue with ${activeKeys.size} team${activeKeys.size > 1 ? "s" : ""} →`}
        </button>
        <button className="btn-ghost" onClick={() => navigate("/feed")}>Skip for now</button>
      </div>
    </div>
  );
}
