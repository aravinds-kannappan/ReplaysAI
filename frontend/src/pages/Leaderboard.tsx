import { useLeaderboard, useMyRank } from "../hooks/usePredictions";
import { useCurrentUser } from "../hooks/useUser";

type LeaderboardEntry = {
  rank: number;
  user_id: number;
  display_name: string;
  avatar_url: string | null;
  total_points: number;
  accuracy: number;
  login_streak: number;
  badges: { slug: string; icon: string }[];
};

export default function Leaderboard() {
  const { data: board = [] } = useLeaderboard() as { data?: LeaderboardEntry[] };
  const { data: myRank } = useMyRank();
  const { data: user } = useCurrentUser();
  const podium = board.slice(0, 3);
  const rivals = myRank?.neighbors ?? board.slice(3, 8);

  return (
    <div className="experience-page league-nba">
      <header className="experience-hero">
        <div>
          <p className="dashboard-kicker">Competition layer</p>
          <h1>Climb through picks, rosters, and streaks</h1>
          <p>Leaders combines prediction accuracy, roster impact, login rhythm, and earned badges into one competitive ladder.</p>
        </div>
        {myRank && <div className="my-rank-chip">Your rank <strong>#{myRank.my_rank}</strong> / {myRank.total_users}</div>}
      </header>

      <section className="podium-grid">
        {podium.map((entry) => (
          <div key={entry.user_id} className={`podium-card rank-${entry.rank}`}>
            <span>#{entry.rank}</span>
            {entry.avatar_url && <img src={entry.avatar_url} alt="" />}
            <strong>{entry.display_name}</strong>
            <b>{entry.total_points.toLocaleString()} pts</b>
            <small>{entry.accuracy}% accuracy · {entry.login_streak} streak</small>
          </div>
        ))}
      </section>

      <section className="leaderboard-layout">
        <div className="dashboard-panel">
          <div className="panel-heading"><div><span>Rivals</span><h2>Near your rank</h2></div></div>
          <div className="rival-list">
            {rivals.map((entry: LeaderboardEntry) => (
              <div key={entry.user_id} className={`rival-row ${entry.user_id === user?.id ? "me" : ""}`}>
                <span>#{entry.rank}</span>
                <strong>{entry.display_name}</strong>
                <b>{entry.total_points.toLocaleString()}</b>
              </div>
            ))}
          </div>
        </div>
        <div className="dashboard-panel">
          <div className="panel-heading"><div><span>Badges</span><h2>Signals that matter</h2></div></div>
          <div className="badge-radar">
            {["First Pick", "Oracle", "Loyal Fan", "Analyst", "Clutch"].map((badge, index) => (
              <div key={badge}><span>{index + 1}</span><strong>{badge}</strong></div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
