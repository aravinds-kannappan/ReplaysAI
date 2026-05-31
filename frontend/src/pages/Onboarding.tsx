import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCurrentUser, useAddFavoriteTeam, useRemoveFavoriteTeam } from "../hooks/useUser";

const NBA_TEAMS = [
  { id: 1, abbr: "ATL", name: "Hawks" }, { id: 2, abbr: "BOS", name: "Celtics" },
  { id: 3, abbr: "BKN", name: "Nets" }, { id: 4, abbr: "CHA", name: "Hornets" },
  { id: 5, abbr: "CHI", name: "Bulls" }, { id: 6, abbr: "CLE", name: "Cavaliers" },
  { id: 7, abbr: "DAL", name: "Mavericks" }, { id: 8, abbr: "DEN", name: "Nuggets" },
  { id: 9, abbr: "DET", name: "Pistons" }, { id: 10, abbr: "GSW", name: "Warriors" },
  { id: 11, abbr: "HOU", name: "Rockets" }, { id: 12, abbr: "IND", name: "Pacers" },
  { id: 13, abbr: "LAC", name: "Clippers" }, { id: 14, abbr: "LAL", name: "Lakers" },
  { id: 15, abbr: "MEM", name: "Grizzlies" }, { id: 16, abbr: "MIA", name: "Heat" },
  { id: 17, abbr: "MIL", name: "Bucks" }, { id: 18, abbr: "MIN", name: "Wolves" },
  { id: 19, abbr: "NOP", name: "Pelicans" }, { id: 20, abbr: "NYK", name: "Knicks" },
  { id: 21, abbr: "OKC", name: "Thunder" }, { id: 22, abbr: "ORL", name: "Magic" },
  { id: 23, abbr: "PHI", name: "76ers" }, { id: 24, abbr: "PHX", name: "Suns" },
  { id: 25, abbr: "POR", name: "Blazers" }, { id: 26, abbr: "SAC", name: "Kings" },
  { id: 27, abbr: "SAS", name: "Spurs" }, { id: 28, abbr: "TOR", name: "Raptors" },
  { id: 29, abbr: "UTA", name: "Jazz" }, { id: 30, abbr: "WAS", name: "Wizards" },
];

export default function Onboarding() {
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const addTeam = useAddFavoriteTeam();
  const removeTeam = useRemoveFavoriteTeam();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [step, setStep] = useState(1);

  // Use actual DB team IDs if available (fallback to local list ordering)
  const favTeamIds = new Set((user?.favorite_teams ?? []).map((t: { id: number }) => t.id));
  const activeIds = selected.size > 0 ? selected : favTeamIds;

  function toggleTeam(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      // Sync from user data first
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

  async function finish() {
    navigate("/feed");
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

      <div className="team-section">
        <h3>NBA</h3>
        <div className="team-grid">
          {NBA_TEAMS.map((t) => {
            // Try to match by abbreviation from actual DB teams
            const dbTeam = (user?.favorite_teams ?? []).find((ft: { abbreviation: string }) => ft.abbreviation === t.abbr);
            const dbId = dbTeam?.id ?? t.id;
            const isSelected = activeIds.has(dbId) || favTeamIds.has(dbId);
            return (
              <button
                key={t.abbr}
                className={`team-chip ${isSelected ? "selected" : ""}`}
                onClick={() => toggleTeam(dbId)}
              >
                <span className="chip-abbr">{t.abbr}</span>
                <span className="chip-name">{t.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="onboarding-footer">
        <button
          className="btn-hero-primary"
          onClick={finish}
          disabled={activeIds.size === 0}
        >
          {activeIds.size === 0 ? "Pick at least one team" : `Continue with ${activeIds.size} team${activeIds.size > 1 ? "s" : ""} →`}
        </button>
        <button className="btn-ghost" onClick={finish}>Skip for now</button>
      </div>
    </div>
  );
}
