import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useGame } from "../hooks/useGames";
import RecapViewer from "../components/RecapViewer";
import HighlightReel from "../components/HighlightReel";
import PlayTimeline from "../components/PlayTimeline";

type Tab = "recap" | "highlights" | "plays";

export default function GameDetail() {
  const { id } = useParams<{ id: string }>();
  const gameId = Number(id);
  const { data: game, isLoading } = useGame(gameId);
  const [tab, setTab] = useState<Tab>("recap");

  if (isLoading) return <div className="page-center">Loading game…</div>;
  if (!game) return <div className="page-center">Game not found.</div>;

  const dateLabel = game.game_date
    ? new Date(game.game_date).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })
    : "";

  return (
    <div className="page-game-detail">
      <Link to="/" className="back-link">← Back to Games</Link>

      <div className="game-header">
        <div className="game-sport-date">
          <span className="sport-tag">{game.sport}</span>
          <span className="game-date">{dateLabel}</span>
          <span className={`badge badge-${game.status}`}>{game.status.toUpperCase()}</span>
        </div>

        <div className="scoreboard">
          <div className="scoreboard-team">
            <span className="sb-abbr">{game.away_team.abbreviation}</span>
            <span className="sb-name">{game.away_team.name}</span>
            <span className={`sb-score ${(game.away_score ?? 0) > (game.home_score ?? 0) ? "score-winner" : ""}`}>
              {game.away_score ?? "—"}
            </span>
          </div>
          <div className="scoreboard-divider">@</div>
          <div className="scoreboard-team">
            <span className="sb-abbr">{game.home_team.abbreviation}</span>
            <span className="sb-name">{game.home_team.name}</span>
            <span className={`sb-score ${(game.home_score ?? 0) > (game.away_score ?? 0) ? "score-winner" : ""}`}>
              {game.home_score ?? "—"}
            </span>
          </div>
        </div>
      </div>

      <div className="tab-bar">
        {(["recap", "highlights", "plays"] as Tab[]).map((t) => (
          <button key={t} className={`tab-btn ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {tab === "recap" && <RecapViewer gameId={gameId} gameStatus={game.status} />}
        {tab === "highlights" && <HighlightReel gameId={gameId} />}
        {tab === "plays" && <PlayTimeline gameId={gameId} />}
      </div>
    </div>
  );
}
