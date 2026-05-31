import { memo } from "react";
import { Link } from "react-router-dom";
import type { Game } from "../types";

interface Props {
  game: Game;
}

function statusBadge(status: string) {
  if (status === "live") return <span className="badge badge-live">LIVE</span>;
  if (status === "final") return <span className="badge badge-final">FINAL</span>;
  return <span className="badge badge-scheduled">UPCOMING</span>;
}

function ScoreCard({ game }: Props) {
  const dateLabel = game.game_date
    ? new Date(game.game_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })
    : "";

  return (
    <Link to={`/game/${game.id}`} className="score-card">
      <div className="score-card-header">
        <span className="sport-tag">{game.sport}</span>
        <span className="game-date">{dateLabel}</span>
        {statusBadge(game.status)}
      </div>
      <div className="score-card-body">
        <div className="team-row">
          <span className="team-abbr">{game.away_team.abbreviation}</span>
          <span className="team-name">{game.away_team.name}</span>
          <span className={`team-score ${(game.away_score ?? 0) > (game.home_score ?? 0) ? "score-winner" : ""}`}>
            {game.away_score ?? "—"}
          </span>
        </div>
        <div className="team-row">
          <span className="team-abbr">{game.home_team.abbreviation}</span>
          <span className="team-name">{game.home_team.name}</span>
          <span className={`team-score ${(game.home_score ?? 0) > (game.away_score ?? 0) ? "score-winner" : ""}`}>
            {game.home_score ?? "—"}
          </span>
        </div>
      </div>
    </Link>
  );
}

export default memo(ScoreCard);
