import { useState } from "react";
import { useCreatePrediction, usePredictions, useUpcomingGames } from "../hooks/usePredictions";
import { useCurrentUser } from "../hooks/useUser";

type League = "NBA" | "NFL";
type UpcomingGame = {
  id: number;
  sport: string;
  game_date: string | null;
  home_team: { id: number; name: string | null };
  away_team: { id: number; name: string | null };
  already_predicted: boolean;
};
type PredictionHistory = {
  id: number;
  is_correct: boolean | null;
  predicted_winner_name: string | null;
  points_earned: number;
  game?: { home_team: string | null; away_team: string | null } | null;
};

export default function Predictions() {
  const [league, setLeague] = useState<League>("NBA");
  const [selected, setSelected] = useState<Record<number, number>>({});
  const { data: user } = useCurrentUser();
  const { data: upcoming = [] } = useUpcomingGames() as { data?: UpcomingGame[] };
  const { data: history = [] } = usePredictions("resolved") as { data?: PredictionHistory[] };
  const createPrediction = useCreatePrediction();
  const games = upcoming.filter((game) => game.sport === league);

  function pick(game: UpcomingGame, teamId: number) {
    if (game.already_predicted || selected[game.id]) return;
    setSelected((prev) => ({ ...prev, [game.id]: teamId }));
    createPrediction.mutate({ game_id: game.id, predicted_winner_team_id: teamId });
  }

  return (
    <div className={`experience-page league-${league.toLowerCase()}`}>
      <header className="experience-hero">
        <div>
          <p className="dashboard-kicker">Picks desk</p>
          <h1>Turn games into conviction</h1>
          <p>Compare matchups, lock picks, and let correct calls push you up the leaderboard.</p>
        </div>
        <div className="league-switch">
          {(["NBA", "NFL"] as League[]).map((item) => (
            <button key={item} className={league === item ? "active" : ""} onClick={() => setLeague(item)}>{item}</button>
          ))}
        </div>
      </header>

      <section className="pick-lab">
        <div className="pick-meter">
          <span>Confidence model</span>
          <strong>{league === "NBA" ? "Shot profile + pace" : "Explosive plays + red zone"}</strong>
          <div className="meter-bars">
            <i /><i /><i /><i />
          </div>
        </div>
        <div className="dashboard-stats">
          <div className="dashboard-stat"><strong>{user?.prediction_accuracy ?? 0}%</strong><span>Accuracy</span></div>
          <div className="dashboard-stat"><strong>{user?.total_points ?? 0}</strong><span>Points</span></div>
          <div className="dashboard-stat"><strong>{history.length}</strong><span>Resolved</span></div>
        </div>
      </section>

      <section className="matchup-board">
        {games.length === 0 && <p className="empty-state">No scheduled {league} games available yet.</p>}
        {games.map((game) => (
          <div key={game.id} className="matchup-card">
            <div className="matchup-top">
              <span>{game.game_date ? new Date(game.game_date).toLocaleString() : "TBD"}</span>
              <b>{game.already_predicted || selected[game.id] ? "Locked" : "Open"}</b>
            </div>
            <div className="matchup-teams">
              {[game.away_team, game.home_team].map((team) => (
                <button
                  key={team.id}
                  className={selected[game.id] === team.id ? "selected" : ""}
                  onClick={() => pick(game, team.id)}
                  disabled={game.already_predicted || !!selected[game.id]}
                >
                  <strong>{team.name}</strong>
                  <span>{team.id === game.away_team.id ? "Away" : "Home"}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
