import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { apiPath } from "../lib/api";
import { useCurrentUser, useAddFavoriteTeam } from "../hooks/useUser";

type Team = {
  id: number;
  abbreviation: string;
  name: string;
  sport: string;
};

export default function Onboarding() {
  const navigate = useNavigate();
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

  function teamKey(team: Team) {
    return `${team.sport}:${team.abbreviation}`;
  }

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

  function continueToFeed() {
    const teams = [...visibleNbaTeams, ...visibleNflTeams].filter((team) => activeKeys.has(teamKey(team)));
    if (!teams.length) return;
    window.localStorage.setItem("replaysai:onboarded", "true");
    window.localStorage.setItem("replaysai:teams", JSON.stringify(teams));
    teams.forEach((team) => addTeam.mutate(team));
    navigate("/feed");
  }

  function TeamSection({ title, emoji, teams, loading }: { title: string; emoji: string; teams: Team[]; loading: boolean }) {
    return (
      <div className="team-section">
        <h3>{emoji} {title}</h3>
        {loading && <p className="loading-text">Syncing live ESPN teams in the background...</p>}
        {teams.length === 0 ? (
          <p className="empty-state">No teams found.</p>
        ) : (
          <div className="team-grid">
            {teams.map((team) => {
              const key = teamKey(team);
              const isSelected = activeKeys.has(key) || favTeamKeys.has(key);
              return (
                <button
                  key={key}
                  className={`team-chip ${isSelected ? "selected" : ""}`}
                  onClick={() => toggleTeam(team)}
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

      <TeamSection title="NBA Teams" emoji="🏀" teams={visibleNbaTeams} loading={nbaLoading} />
      <TeamSection title="NFL Teams" emoji="🏈" teams={visibleNflTeams} loading={nflLoading} />

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
