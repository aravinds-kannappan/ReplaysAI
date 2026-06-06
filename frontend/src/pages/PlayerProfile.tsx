import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { apiPath } from "../lib/api";

interface PlayerData {
  id: number;
  name: string;
  position: string;
  jersey_number: number | null;
  team: { id: number; name: string | null };
  play_stats: Record<string, number>;
  total_plays: number;
}

export default function PlayerProfile() {
  const { id } = useParams<{ id: string }>();
  const { data: player, isLoading } = useQuery<PlayerData>({
    queryKey: ["player", id],
    queryFn: () => axios.get(apiPath(`/api/players/${id}`)).then((r) => r.data),
  });

  if (isLoading) return <div className="page-center">Loading player…</div>;
  if (!player) return <div className="page-center">Player not found.</div>;

  const statEntries = Object.entries(player.play_stats).sort((a, b) => b[1] - a[1]);

  return (
    <div className="page-player">
      <Link to="/" className="back-link">← Back to Games</Link>

      <div className="player-header">
        <div className="player-number">#{player.jersey_number ?? "—"}</div>
        <div>
          <h1>{player.name}</h1>
          <p className="player-meta">{player.position} · {player.team.name}</p>
        </div>
      </div>

      <div className="player-stats">
        <h3>Play Stats</h3>
        <table className="stats-table">
          <thead><tr><th>Play Type</th><th>Count</th></tr></thead>
          <tbody>
            {statEntries.map(([type, count]) => (
              <tr key={type}>
                <td>{type.replace(/_/g, " ")}</td>
                <td>{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="total-plays">Total plays tracked: {player.total_plays}</p>
      </div>
    </div>
  );
}
