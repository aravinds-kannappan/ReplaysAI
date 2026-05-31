import { Link } from "react-router-dom";
import { useFeed } from "../hooks/usePredictions";
import { useCurrentUser } from "../hooks/useUser";
import ScoreCard from "../components/ScoreCard";
import type { Game } from "../types";

function StreakBar({ streak, points }: { streak: number; points: number }) {
  return (
    <div className="streak-bar">
      <div className="streak-item">
        <span className="streak-fire">🔥</span>
        <span className="streak-value">{streak}</span>
        <span className="streak-label">Day Streak</span>
      </div>
      <div className="streak-divider" />
      <div className="streak-item">
        <span className="streak-fire">⭐</span>
        <span className="streak-value">{points}</span>
        <span className="streak-label">Points</span>
      </div>
    </div>
  );
}

export default function Feed() {
  const { data: user } = useCurrentUser();
  const { data: feed, isLoading } = useFeed();

  const games: Game[] = feed?.games ?? [];
  const onboarded = feed?.onboarded ?? false;

  return (
    <div className="page-feed">
      {user && (
        <div className="feed-header">
          <div>
            <h2>Hey {user.display_name || user.username || "Fan"} 👋</h2>
            <p className="feed-sub">
              {onboarded
                ? `Games from your ${user.favorite_teams?.length ?? 0} favorite team${(user.favorite_teams?.length ?? 0) > 1 ? "s" : ""}`
                : "Complete onboarding to personalize your feed"}
            </p>
          </div>
          <StreakBar streak={user.login_streak ?? 0} points={user.total_points ?? 0} />
        </div>
      )}

      {!onboarded && (
        <div className="onboard-prompt">
          <span>🏀</span>
          <div>
            <strong>Pick your teams</strong>
            <p>Personalize your feed, recaps, and predictions.</p>
          </div>
          <Link to="/onboarding" className="btn-primary">Choose Teams →</Link>
        </div>
      )}

      <div className="feed-quick-actions">
        <Link to="/predictions" className="quick-card">
          <span>🎯</span>
          <strong>Make a Pick</strong>
          <span className="quick-sub">Predict today's games</span>
        </Link>
        <Link to="/roster" className="quick-card">
          <span>📋</span>
          <strong>My Roster</strong>
          <span className="quick-sub">Build this week's lineup</span>
        </Link>
        <Link to="/leaderboard" className="quick-card">
          <span>🏆</span>
          <strong>Leaderboard</strong>
          <span className="quick-sub">See your rank</span>
        </Link>
      </div>

      <section className="feed-games">
        <h3>{onboarded ? "Your Teams' Games" : "Recent Games"}</h3>
        {isLoading && <p className="loading-text">Loading games…</p>}
        {!isLoading && games.length === 0 && (
          <p className="empty-state">No recent games found. Check back soon.</p>
        )}
        <div className="games-grid">
          {games.map((g) => <ScoreCard key={g.id} game={g} />)}
        </div>
      </section>
    </div>
  );
}
