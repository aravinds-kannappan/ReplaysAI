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
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const { data: nbaTeams = [], isLoading: nbaLoading } = useQuery<Team[]>({
    queryKey: ["teams", "NBA"],
    queryFn: () => axios.get(apiPath("/api/teams"), { params: { sport: "NBA" } }).then((r) => r.data),
  });

  const { data: nflTeams = [], isLoading: nflLoading } = useQuery<Team[]>({
    queryKey: ["teams", "NFL"],
    queryFn: () => axios.get(apiPath("/api/teams"), { params: { sport: "NFL" } }).then((r) => r.data),
  });

  const favoriteTeams = (user?.favorite_teams ?? []) as { id: number }[];
  const favTeamIds = new Set<number>(favoriteTeams.map((t) => t.id));
  const activeIds = selected.size > 0 ? selected : favTeamIds;
  const visibleNbaTeams = nbaTeams;
  const visibleNflTeams = nflTeams;

  function toggleTeam(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      favTeamIds.forEach((tid) => next.add(tid));
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function continueToFeed() {
    const ids = Array.from(activeIds);
    if (!ids.length) return;
    window.localStorage.setItem("replaysai:onboarded", "true");
    window.localStorage.setItem("replaysai:teamIds", JSON.stringify(ids));
    ids.forEach((id) => addTeam.mutate(id));
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
              const isSelected = activeIds.has(team.id) || favTeamIds.has(team.id);
              return (
                <button
                  key={team.id}
                  className={`team-chip ${isSelected ? "selected" : ""}`}
                  onClick={() => toggleTeam(team.id)}
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
          disabled={activeIds.size === 0}
        >
          {activeIds.size === 0
            ? "Pick at least one team"
            : `Continue with ${activeIds.size} team${activeIds.size > 1 ? "s" : ""} →`}
        </button>
        <button className="btn-ghost" onClick={() => navigate("/feed")}>Skip for now</button>
      </div>
    </div>
  );
}
