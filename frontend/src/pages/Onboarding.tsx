import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { apiPath } from "../lib/api";
import { useCurrentUser, useAddFavoriteTeam, useRemoveFavoriteTeam } from "../hooks/useUser";

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
  const removeTeam = useRemoveFavoriteTeam();
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

  function toggleTeam(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      favTeamIds.forEach((tid) => next.add(tid));
      if (next.has(id)) {
        next.delete(id);
        removeTeam.mutate(id);
      } else {
        next.add(id);
        addTeam.mutate(id);
      }
      return next;
    });
  }

  function TeamSection({ title, emoji, teams, loading }: { title: string; emoji: string; teams: Team[]; loading: boolean }) {
    return (
      <div className="team-section">
        <h3>{emoji} {title}</h3>
        {loading ? (
          <p className="loading-text">Loading teams…</p>
        ) : teams.length === 0 ? (
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
        <h1>Pick your teams</h1>
        <p>We'll personalize your feed, recaps, and predictions around them.</p>
        <div className="onboarding-steps">
          <span className="step active">1. Choose Teams</span>
          <span className="step-arrow">→</span>
          <span className="step">2. Your Feed</span>
        </div>
      </div>

      <TeamSection title="NBA Teams" emoji="🏀" teams={nbaTeams} loading={nbaLoading} />
      <TeamSection title="NFL Teams" emoji="🏈" teams={nflTeams} loading={nflLoading} />

      <div className="onboarding-footer">
        <button
          className="btn-hero-primary"
          onClick={() => navigate("/feed")}
          disabled={activeIds.size === 0}
        >
          {activeIds.size === 0
            ? "Pick at least one team"
            : `Continue with ${activeIds.size} team${activeIds.size > 1 ? "s" : ""} →`}
        </button>
        <button className="btn-ghost" onClick={() => navigate("/feed")}>
          Skip for now
        </button>
      </div>
    </div>
  );
}
