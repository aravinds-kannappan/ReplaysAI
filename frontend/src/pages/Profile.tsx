import { useCurrentUser, useNotifications } from "../hooks/useUser";
import { usePredictions } from "../hooks/usePredictions";
import { useAuth } from "../lib/auth";
import axios from "axios";
import { apiPath } from "../lib/api";

type FavoriteTeam = {
  id: number;
  name: string;
  abbreviation: string;
  sport: string;
};

type Badge = {
  slug: string;
  name: string;
  icon: string;
};

type Notification = {
  id: number;
  title: string;
  body: string;
  read: boolean;
};

type Prediction = {
  id: number;
  resolved_at: string | null;
  is_correct: boolean | null;
  points_earned: number;
  game?: {
    home_team: string | null;
    away_team: string | null;
  } | null;
};

export default function Profile() {
  const { data: user, isLoading } = useCurrentUser();
  const { data: predictions = [] } = usePredictions() as { data?: Prediction[] };
  const { data: notifs = [] } = useNotifications() as { data?: Notification[] };
  const { getToken } = useAuth();

  async function markRead(id: number) {
    const token = await getToken();
    await axios.post(apiPath(`/api/users/me/notifications/${id}/read`), {}, { headers: { Authorization: `Bearer ${token}` } });
  }

  if (isLoading) return <div className="page-center">Loading profile…</div>;
  if (!user) return null;

  const badges = user.badges ?? [];
  const unread = notifs.filter((n) => !n.read);
  const resolved = predictions.filter((p) => p.resolved_at);
  const correct = resolved.filter((p) => p.is_correct).length;

  return (
    <div className="page-profile">
      <div className="profile-header">
        {user.avatar_url && <img src={user.avatar_url} alt="" className="profile-avatar" />}
        <div>
          <h2>{user.display_name || user.username || `Fan #${user.id}`}</h2>
          {user.bio && <p className="profile-bio">{user.bio}</p>}
          <div className="profile-stats">
            <span>⭐ {user.total_points} pts</span>
            <span>🔥 {user.login_streak}-day streak</span>
            <span>🎯 {user.prediction_accuracy}% accuracy</span>
          </div>
        </div>
      </div>

      {/* Favorite teams */}
      {user.favorite_teams?.length > 0 && (
        <section className="profile-section">
          <h3>My Teams</h3>
          <div className="team-chips-row">
            {(user.favorite_teams as FavoriteTeam[]).map((t) => (
              <span key={`${t.sport}:${t.abbreviation}`} className="team-chip selected">
                <span className="chip-abbr">{t.abbreviation}</span>
                <span className="chip-name">{t.name}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Badges */}
      <section className="profile-section">
        <h3>Badges {badges.length > 0 ? `(${badges.length})` : ""}</h3>
        {badges.length === 0 ? (
          <p className="empty-state">No badges yet — make predictions and log in daily to earn them!</p>
        ) : (
          <div className="badges-grid">
            {(badges as Badge[]).map((b) => (
              <div key={b.slug} className="badge-card">
                <span className="badge-icon">{b.icon}</span>
                <span className="badge-name">{b.name}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Prediction history */}
      <section className="profile-section">
        <h3>Predictions ({correct}/{resolved.length} correct)</h3>
        {resolved.length === 0 ? (
          <p className="empty-state">No resolved predictions yet.</p>
        ) : (
          <div className="history-list">
            {resolved.slice(0, 8).map((p) => (
              <div key={p.id} className={`history-item ${p.is_correct ? "correct" : "incorrect"}`}>
                <span>{p.is_correct ? "✅" : "❌"}</span>
                <span>{p.game?.away_team} @ {p.game?.home_team}</span>
                <span className="history-pts">{p.points_earned > 0 ? `+${p.points_earned} pts` : ""}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Notifications */}
      {notifs.length > 0 && (
        <section className="profile-section">
          <h3>Notifications {unread.length > 0 ? `(${unread.length} unread)` : ""}</h3>
          <div className="notif-list">
            {notifs.slice(0, 10).map((n) => (
              <div key={n.id} className={`notif-item ${n.read ? "" : "unread"}`} onClick={() => !n.read && markRead(n.id)}>
                <strong>{n.title}</strong>
                <p>{n.body}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
