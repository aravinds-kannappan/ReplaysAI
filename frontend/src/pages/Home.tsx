import { useState } from "react";
import { useGames } from "../hooks/useGames";
import { useRankings } from "../hooks/useLiveScores";
import ScoreCard from "../components/ScoreCard";
import type { Standing } from "../types";

function StandingsTable({ sport, standings }: { sport: string; standings: Standing[] }) {
  const top = standings.slice(0, 8);
  return (
    <div className="standings-section">
      <h3>{sport} Standings</h3>
      <table className="standings-table">
        <thead>
          <tr><th>Team</th><th>W</th><th>L</th><th>PCT</th></tr>
        </thead>
        <tbody>
          {top.map((s) => (
            <tr key={s.team_id}>
              <td>{s.abbreviation}</td>
              <td>{s.wins}</td>
              <td>{s.losses}</td>
              <td>{s.win_pct.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Home() {
  const [sport, setSport] = useState<string>("NBA");
  const { data: gamesData, isLoading: gamesLoading } = useGames({ sport, limit: 20 });
  const { data: rankings } = useRankings(sport);

  const standings = sport === "NBA" ? rankings?.NBA : rankings?.NFL;

  return (
    <div className="page-home">
      <header className="site-header">
        <h1>Replays AI</h1>
        <p className="tagline">Multimodal sports recaps. Real data. Real highlights.</p>
      </header>

      <div className="sport-tabs">
        {["NBA", "NFL"].map((s) => (
          <button
            key={s}
            className={`sport-tab ${sport === s ? "active" : ""}`}
            onClick={() => setSport(s)}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="home-layout">
        <section className="games-section">
          <h2>Recent Games</h2>
          {gamesLoading && <p className="loading-text">Loading games…</p>}
          {!gamesLoading && (!gamesData?.games.length) && (
            <p className="empty-state">No games returned yet. ReplaysAI is syncing ESPN public schedules and stored ingestions.</p>
          )}
          <div className="games-grid">
            {gamesData?.games.map((g) => <ScoreCard key={g.id} game={g} />)}
          </div>
        </section>

        <aside className="sidebar">
          {standings && standings.length > 0 && (
            <StandingsTable sport={sport} standings={standings} />
          )}
        </aside>
      </div>
    </div>
  );
}
