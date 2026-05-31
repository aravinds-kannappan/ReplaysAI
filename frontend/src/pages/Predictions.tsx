import { useState } from "react";
import { usePredictions, useUpcomingGames, useCreatePrediction } from "../hooks/usePredictions";
import { useCurrentUser } from "../hooks/useUser";

function PredictionCard({ game, onPick }: { game: any; onPick: (winnerId: number) => void }) {
  const [picked, setPicked] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(game.already_predicted);

  function handlePick(id: number) {
    if (submitted) return;
    setPicked(id);
    onPick(id);
    setSubmitted(true);
  }

  const date = game.game_date ? new Date(game.game_date).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "";

  return (
    <div className={`prediction-card ${submitted ? "submitted" : ""}`}>
      <div className="pred-meta">{game.sport} · {date}</div>
      <div className="pred-teams">
        <button
          className={`team-pick ${picked === game.away_team.id ? "selected" : ""} ${submitted && picked !== game.away_team.id ? "dimmed" : ""}`}
          onClick={() => handlePick(game.away_team.id)}
          disabled={submitted}
        >
          <span className="pick-name">{game.away_team.name}</span>
          <span className="pick-label">Away</span>
        </button>
        <span className="vs">VS</span>
        <button
          className={`team-pick ${picked === game.home_team.id ? "selected" : ""} ${submitted && picked !== game.home_team.id ? "dimmed" : ""}`}
          onClick={() => handlePick(game.home_team.id)}
          disabled={submitted}
        >
          <span className="pick-name">{game.home_team.name}</span>
          <span className="pick-label">Home</span>
        </button>
      </div>
      {submitted && <p className="pred-submitted">Pick locked ✓</p>}
    </div>
  );
}

export default function Predictions() {
  const { data: user } = useCurrentUser();
  const { data: upcoming = [] } = useUpcomingGames();
  const { data: history = [] } = usePredictions("resolved");
  const createPrediction = useCreatePrediction();

  const accuracy = user ? user.prediction_accuracy : 0;
  const streak = user?.streaks?.prediction_streak ?? 0;

  function handlePick(gameId: number, winnerId: number) {
    createPrediction.mutate({ game_id: gameId, predicted_winner_team_id: winnerId });
  }

  return (
    <div className="page-predictions">
      <div className="pred-header">
        <h2>Predictions</h2>
        <div className="pred-stats">
          <div className="pred-stat">
            <span className="stat-big">{accuracy}%</span>
            <span className="stat-small">Accuracy</span>
          </div>
          <div className="pred-stat">
            <span className="stat-big">🔥{streak}</span>
            <span className="stat-small">Correct Streak</span>
          </div>
          <div className="pred-stat">
            <span className="stat-big">⭐{user?.total_points ?? 0}</span>
            <span className="stat-small">Points</span>
          </div>
        </div>
      </div>

      <section className="pred-section">
        <h3>Upcoming Games</h3>
        {upcoming.length === 0 ? (
          <p className="empty-state">No upcoming games to predict right now. Check back later.</p>
        ) : (
          <div className="pred-grid">
            {upcoming.map((g: any) => (
              <PredictionCard key={g.id} game={g} onPick={(wid) => handlePick(g.id, wid)} />
            ))}
          </div>
        )}
      </section>

      {history.length > 0 && (
        <section className="pred-section">
          <h3>Past Picks</h3>
          <div className="history-list">
            {history.slice(0, 10).map((p: any) => (
              <div key={p.id} className={`history-item ${p.is_correct ? "correct" : "incorrect"}`}>
                <span className="history-result">{p.is_correct ? "✅" : "❌"}</span>
                <span className="history-game">{p.game?.away_team} @ {p.game?.home_team}</span>
                <span className="history-pick">Picked: {p.predicted_winner_name}</span>
                <span className="history-pts">{p.points_earned > 0 ? `+${p.points_earned} pts` : ""}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
