import { useMemo, useState } from "react";
import { useRosterPlayers, useRosters, useSaveRoster } from "../hooks/usePredictions";

type League = "NBA" | "NFL";
type RosterPlayer = { id: number; name: string; position: string | null; team: string | null; impact_score: number; headshot?: string | null };
type Roster = { sport: string; player_ids?: number[]; total_points: number; locked: boolean };

const MAX_PLAYERS = 8;

export default function RosterBuilder() {
  const [league, setLeague] = useState<League>("NBA");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const { data: players = [], isLoading } = useRosterPlayers(league) as { data?: RosterPlayer[]; isLoading: boolean };
  const { data: rosters = [] } = useRosters() as { data?: Roster[] };
  const saveRoster = useSaveRoster();
  const selectedPlayers = selectedIds.map((id) => players.find((player) => player.id === id)).filter(Boolean) as RosterPlayer[];
  const opponent = players.filter((player) => !selectedIds.includes(player.id)).slice(0, selectedPlayers.length || 4);
  const myScore = useMemo(() => selectedPlayers.reduce((sum, player) => sum + player.impact_score, 0), [selectedPlayers]);
  const oppScore = opponent.reduce((sum, player) => sum + player.impact_score, 0);
  const currentWeekRoster = rosters.find((roster) => roster.sport === league);

  function toggle(id: number) {
    setSelectedIds((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : prev.length < MAX_PLAYERS ? [...prev, id] : prev);
  }

  async function save() {
    await saveRoster.mutateAsync({ sport: league, player_ids: selectedIds });
  }

  return (
    <div className={`experience-page league-${league.toLowerCase()}`}>
      <header className="experience-hero">
        <div>
          <p className="dashboard-kicker">Fantasy arena</p>
          <h1>Build a roster, then run the matchup</h1>
          <p>Draft players from live ESPN stat fallbacks, compare impact, and save the lineup for this week.</p>
        </div>
        <div className="league-switch">
          {(["NBA", "NFL"] as League[]).map((item) => (
            <button key={item} className={league === item ? "active" : ""} onClick={() => { setLeague(item); setSelectedIds([]); }}>{item}</button>
          ))}
        </div>
      </header>

      <section className="versus-stage">
        <div className="versus-side">
          <span>Your roster</span>
          <strong>{Math.round(myScore)}</strong>
          <p>{selectedPlayers.length}/{MAX_PLAYERS} players selected</p>
        </div>
        <div className="versus-core">VS</div>
        <div className="versus-side">
          <span>Projected opponent</span>
          <strong>{Math.round(oppScore)}</strong>
          <p>{opponent.length} comparable players</p>
        </div>
      </section>

      {currentWeekRoster && (
        <div className="current-roster">
          <strong>This week:</strong> {currentWeekRoster.player_ids?.length ?? 0} players · {currentWeekRoster.total_points} pts
          {currentWeekRoster.locked && <span className="locked-badge">Locked</span>}
        </div>
      )}

      <section className="fantasy-grid">
        <div className="dashboard-panel">
          <div className="panel-heading"><div><span>{league} pool</span><h2>Available players</h2></div></div>
          {isLoading && <p className="loading-text">Loading players...</p>}
          <div className="player-market">
            {players.slice(0, 30).map((player) => (
              <button key={player.id} className={selectedIds.includes(player.id) ? "selected" : ""} onClick={() => toggle(player.id)}>
                {player.headshot && <img src={player.headshot} alt="" />}
                <span><strong>{player.name}</strong><small>{player.team || "FA"} · {player.position || "UTIL"}</small></span>
                <b>{player.impact_score}</b>
              </button>
            ))}
          </div>
        </div>

        <aside className="dashboard-panel">
          <div className="panel-heading"><div><span>Lineup</span><h2>My squad</h2></div></div>
          <div className="my-picks">
            {selectedPlayers.map((player) => <div key={player.id} className="pick-item"><span>{player.name}</span><button onClick={() => toggle(player.id)}>x</button></div>)}
            {selectedPlayers.length === 0 && <p className="empty-state">Tap players to draft them.</p>}
          </div>
          <button className="btn-primary" disabled={selectedIds.length === 0 || saveRoster.isPending} onClick={save}>
            {saveRoster.isPending ? "Saving..." : "Save lineup"}
          </button>
        </aside>
      </section>
    </div>
  );
}
