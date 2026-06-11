import { memo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import ReelPlayer, { type Clip, type Playlist } from "./ReelPlayer";
import { apiPath } from "../lib/api";

interface Props {
  gameId: number;
}

type Cut = {
  label: string;
  estimated_seconds: number;
  status: string;
  clips: Clip[];
};

function HighlightReel({ gameId }: Props) {
  const [playlist, setPlaylist] = useState<Playlist | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["reel-cuts", gameId],
    queryFn: () => axios.get(apiPath(`/api/games/${gameId}/reels`)).then((r) => r.data),
    staleTime: 300_000,
  });

  if (isLoading) return <div className="highlight-placeholder">Loading highlight clips...</div>;
  if (!data) return null;

  const cuts: Cut[] = data.cuts ?? [];
  const playableCuts = cuts.filter((cut) => cut.clips?.length);

  return (
    <div className="highlight-reel">
      {playlist && <ReelPlayer playlist={playlist} onClose={() => setPlaylist(null)} />}

      {playableCuts.length > 0 ? (
        <div className="summary-list">
          {playableCuts.map((cut) => (
            <div key={cut.label} className="summary-row reel-cut-row">
              <div>
                <strong>{cut.label} · {cut.clips.length} clips · {cut.estimated_seconds}s of video</strong>
                <span>{cut.clips.slice(0, 2).map((clip) => clip.headline).join(" | ")}</span>
              </div>
              <button
                className="btn-primary reel-play-btn"
                onClick={() => setPlaylist({ label: cut.label, clips: cut.clips })}
              >
                ▶ Play reel
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-state">
          ESPN has not published video clips for this game yet. Clips usually appear shortly after tip-off.
        </p>
      )}

      <Link to="/reels" className="btn-ghost">Open the reel studio for custom cuts →</Link>
    </div>
  );
}

export default memo(HighlightReel);
