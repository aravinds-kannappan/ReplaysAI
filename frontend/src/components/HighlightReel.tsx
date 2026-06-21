import { memo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import StoryReelPlayer, { type Story } from "./StoryReelPlayer";
import { useGame } from "../hooks/useGames";
import { apiPath } from "../lib/api";

interface Props {
  gameId: number;
}

type Cut = { label: string; duration_seconds: number; story: Story };

function HighlightReel({ gameId }: Props) {
  const [story, setStory] = useState<Story | null>(null);
  const { data: game } = useGame(gameId);
  const { data, isLoading } = useQuery({
    queryKey: ["reel-cuts", gameId],
    queryFn: () => axios.get(apiPath(`/api/games/${gameId}/reels`)).then((r) => r.data),
    staleTime: 300_000,
  });

  if (isLoading) return <div className="highlight-placeholder">Building story reels from the play-by-play...</div>;
  if (!data) return null;

  const cuts: Cut[] = data.cuts ?? [];

  return (
    <div className="highlight-reel">
      {story && (
        <StoryReelPlayer
          story={story}
          awayAbbr={game?.away_team.abbreviation || "AWY"}
          homeAbbr={game?.home_team.abbreviation || "HME"}
          onClose={() => setStory(null)}
        />
      )}

      <div className="summary-list">
        {cuts.map((cut) => (
          <div key={cut.label} className="summary-row reel-cut-row">
            <div>
              <strong>{cut.label} · {cut.story.scene_count} scenes</strong>
              <span>{cut.story.title}</span>
            </div>
            <button className="btn-primary reel-play-btn" onClick={() => setStory(cut.story)}>
              ▶ Play story
            </button>
          </div>
        ))}
        {cuts.length === 0 && <p className="empty-state">Play-by-play has not published for this game yet.</p>}
      </div>

      <Link to={`/reel/${gameId}`} className="btn-primary">▶ Open narrated reel — interrupt &amp; ask anytime →</Link>
    </div>
  );
}

export default memo(HighlightReel);
