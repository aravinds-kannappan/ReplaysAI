import { useLeaderboard, useMyRank } from "../hooks/usePredictions";
import { useCurrentUser } from "../hooks/useUser";

export default function Leaderboard() {
  const { data: board = [] } = useLeaderboard();
  const { data: myRank } = useMyRank();
  const { data: user } = useCurrentUser();

  return (
    <div className="page-leaderboard">
      <div className="lb-header">
        <h2>🏆 Leaderboard</h2>
        {myRank && (
          <div className="my-rank-chip">
            Your rank: <strong>#{myRank.my_rank}</strong> of {myRank.total_users}
          </div>
        )}
      </div>

      <div className="lb-table">
        <div className="lb-row lb-header-row">
          <span>#</span>
          <span>Fan</span>
          <span>Points</span>
          <span>Accuracy</span>
          <span>Streak</span>
          <span>Badges</span>
        </div>
        {board.map((entry: any) => (
          <div
            key={entry.user_id}
            className={`lb-row ${entry.user_id === user?.id ? "lb-me" : ""}`}
          >
            <span className={`lb-rank ${entry.rank <= 3 ? "lb-top" : ""}`}>
              {entry.rank === 1 ? "🥇" : entry.rank === 2 ? "🥈" : entry.rank === 3 ? "🥉" : `#${entry.rank}`}
            </span>
            <span className="lb-user">
              {entry.avatar_url && <img src={entry.avatar_url} alt="" className="lb-avatar" />}
              {entry.display_name}
            </span>
            <span className="lb-pts">{entry.total_points.toLocaleString()}</span>
            <span className="lb-acc">{entry.accuracy}%</span>
            <span className="lb-streak">🔥{entry.login_streak}</span>
            <span className="lb-badges">
              {entry.badges.slice(0, 3).map((b: any) => (
                <span key={b.slug} title={b.slug}>{b.icon}</span>
              ))}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
