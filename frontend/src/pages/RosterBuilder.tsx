import { useState } from "react";
import { useRosters, useRosterPlayers, useSaveRoster } from "../hooks/usePredictions";

const MAX_PLAYERS = 8;

type RosterPlayer = {
  id: number;
  name: string;
  position: string | null;
  team: string | null;
  impact_score: number;
};

type Roster = {
  sport: string;
  player_ids?: number[];
  total_points: number;
  locked: boolean;
};

export default function RosterBuilder() {
  const [sport, setSport] = useState("NBA");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [saved, setSaved] = useState(false);
  const { data: players = [], isLoading } = useRosterPlayers(sport) as { data?: RosterPlayer[]; isLoading: boolean };
  const { data: rosters = [] } = useRosters() as { data?: Roster[] };
  const saveRoster = useSaveRoster();

  function toggle(id: number) {
    setSaved(false);
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < MAX_PLAYERS ? [...prev, id] : prev
    );
  }

  async function handleSave() {
    await saveRoster.mutateAsync({ sport, player_ids: selectedIds });
    setSaved(true);
  }

  const currentWeekRoster = rosters.find((r) => r.sport === sport);

  return (
    <div className="page-roster">
      <div className="roster-header">
        <h2>📋 Weekly Roster</h2>
        <p>Pick up to {MAX_PLAYERS} players. Points scored based on real play-by-play performance.</p>
        <div className="sport-tabs">
          {["NBA", "NFL"].map((s) => (
            <button key={s} className={`sport-tab ${sport === s ? "active" : ""}`} onClick={() => { setSport(s); setSelectedIds([]); }}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {currentWeekRoster && (
        <div className="current-roster">
          <strong>This week's roster:</strong> {currentWeekRoster.player_ids?.length ?? 0} players · {currentWeekRoster.total_points} pts
          {currentWeekRoster.locked && <span className="locked-badge">🔒 Locked</span>}
        </div>
      )}

      <div className="roster-layout">
        <div className="players-list">
          <h3>Available Players</h3>
          {isLoading && <p className="loading-text">Loading players…</p>}
          {players.map((p) => {
            const isSelected = selectedIds.includes(p.id);
            const canSelect = isSelected || selectedIds.length < MAX_PLAYERS;
            return (
              <div key={p.id} className={`player-row ${isSelected ? "selected" : ""} ${!canSelect ? "disabled" : ""}`} onClick={() => canSelect && toggle(p.id)}>
                <div className="player-info">
                  <span className="player-name">{p.name}</span>
                  <span className="player-meta">{p.team} · {p.position || "?"}</span>
                </div>
                <div className="player-score">
                  <span className="impact">{p.impact_score}</span>
                  <span className="impact-label">impact/game</span>
                </div>
                {isSelected && <span className="selected-check">✓</span>}
              </div>
            );
          })}
        </div>

        <div className="roster-sidebar">
          <h3>My Picks ({selectedIds.length}/{MAX_PLAYERS})</h3>
          {selectedIds.length === 0 ? (
            <p className="empty-state">Click players to add them</p>
          ) : (
            <div className="my-picks">
              {selectedIds.map((id) => {
                const p = players.find((pl) => pl.id === id);
                return p ? (
                  <div key={id} className="pick-item">
                    <span>{p.name}</span>
                    <button className="remove-pick" onClick={() => toggle(id)}>×</button>
                  </div>
                ) : null;
              })}
            </div>
          )}
          <button
            className="btn-hero-primary"
            onClick={handleSave}
            disabled={selectedIds.length === 0 || saveRoster.isPending || saved}
          >
            {saved ? "✓ Saved!" : saveRoster.isPending ? "Saving…" : "Save Roster"}
          </button>
        </div>
      </div>
    </div>
  );
}
