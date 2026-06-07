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

const NBA_FALLBACK_TEAMS: Team[] = [
  ["ATL", "Atlanta Hawks"], ["BOS", "Boston Celtics"], ["BKN", "Brooklyn Nets"], ["CHA", "Charlotte Hornets"],
  ["CHI", "Chicago Bulls"], ["CLE", "Cleveland Cavaliers"], ["DAL", "Dallas Mavericks"], ["DEN", "Denver Nuggets"],
  ["DET", "Detroit Pistons"], ["GSW", "Golden State Warriors"], ["HOU", "Houston Rockets"], ["IND", "Indiana Pacers"],
  ["LAC", "LA Clippers"], ["LAL", "Los Angeles Lakers"], ["MEM", "Memphis Grizzlies"], ["MIA", "Miami Heat"],
  ["MIL", "Milwaukee Bucks"], ["MIN", "Minnesota Timberwolves"], ["NOP", "New Orleans Pelicans"], ["NYK", "New York Knicks"],
  ["OKC", "Oklahoma City Thunder"], ["ORL", "Orlando Magic"], ["PHI", "Philadelphia 76ers"], ["PHX", "Phoenix Suns"],
  ["POR", "Portland Trail Blazers"], ["SAC", "Sacramento Kings"], ["SAS", "San Antonio Spurs"], ["TOR", "Toronto Raptors"],
  ["UTA", "Utah Jazz"], ["WAS", "Washington Wizards"],
].map(([abbreviation, name], index) => ({ id: 1001 + index, abbreviation, name, sport: "NBA" }));

const NFL_FALLBACK_TEAMS: Team[] = [
  ["ARI", "Arizona Cardinals"], ["ATL", "Atlanta Falcons"], ["BAL", "Baltimore Ravens"], ["BUF", "Buffalo Bills"],
  ["CAR", "Carolina Panthers"], ["CHI", "Chicago Bears"], ["CIN", "Cincinnati Bengals"], ["CLE", "Cleveland Browns"],
  ["DAL", "Dallas Cowboys"], ["DEN", "Denver Broncos"], ["DET", "Detroit Lions"], ["GB", "Green Bay Packers"],
  ["HOU", "Houston Texans"], ["IND", "Indianapolis Colts"], ["JAX", "Jacksonville Jaguars"], ["KC", "Kansas City Chiefs"],
  ["LV", "Las Vegas Raiders"], ["LAC", "Los Angeles Chargers"], ["LAR", "Los Angeles Rams"], ["MIA", "Miami Dolphins"],
  ["MIN", "Minnesota Vikings"], ["NE", "New England Patriots"], ["NO", "New Orleans Saints"], ["NYG", "New York Giants"],
  ["NYJ", "New York Jets"], ["PHI", "Philadelphia Eagles"], ["PIT", "Pittsburgh Steelers"], ["SF", "San Francisco 49ers"],
  ["SEA", "Seattle Seahawks"], ["TB", "Tampa Bay Buccaneers"], ["TEN", "Tennessee Titans"], ["WAS", "Washington Commanders"],
].map(([abbreviation, name], index) => ({ id: 2001 + index, abbreviation, name, sport: "NFL" }));

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
  const visibleNbaTeams = nbaTeams.length ? nbaTeams : NBA_FALLBACK_TEAMS;
  const visibleNflTeams = nflTeams.length ? nflTeams : NFL_FALLBACK_TEAMS;

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

      <TeamSection title="NBA Teams" emoji="🏀" teams={visibleNbaTeams} loading={nbaLoading && nbaTeams.length === 0} />
      <TeamSection title="NFL Teams" emoji="🏈" teams={visibleNflTeams} loading={nflLoading && nflTeams.length === 0} />

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
