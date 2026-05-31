import { memo } from "react";
import { useHighlights } from "../hooks/useGames";

interface Props {
  gameId: number;
}

const PLAY_EMOJI: Record<string, string> = {
  dunk: "🏀",
  three_pointer: "🎯",
  block: "✋",
  steal: "💨",
  touchdown: "🏈",
  interception: "🔄",
  field_goal: "🎯",
  sack: "💥",
  other: "▶️",
  crowd_reaction: "📣",
};

function getYouTubeEmbedUrl(url: string | null): string | null {
  if (!url) return null;
  const match = url.match(/[?&]v=([^&]+)/);
  if (match) return `https://www.youtube.com/embed/${match[1]}`;
  return null;
}

function HighlightReel({ gameId }: Props) {
  const { data, isLoading } = useHighlights(gameId);

  if (isLoading) return <div className="highlight-placeholder">Loading highlights...</div>;
  if (!data) return null;

  const embedUrl = getYouTubeEmbedUrl(data.video_url);
  const topClips = data.classifications.filter((c) => c.confidence > 0.6 && c.play_type !== "other").slice(0, 12);

  return (
    <div className="highlight-reel">
      {embedUrl ? (
        <div className="video-embed">
          <iframe
            src={embedUrl}
            title="Game Highlights"
            allowFullScreen
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          />
        </div>
      ) : data.video_url ? (
        <a href={data.video_url} target="_blank" rel="noopener noreferrer" className="video-search-link">
          Search for highlights on YouTube →
        </a>
      ) : null}

      {topClips.length > 0 && (
        <div className="cv-timeline">
          <h4>CV-Detected Plays</h4>
          <div className="timeline-items">
            {topClips.map((c, i) => (
              <div key={i} className="timeline-item">
                <span className="play-emoji">{PLAY_EMOJI[c.play_type] ?? "▶️"}</span>
                <span className="play-label">{c.play_type.replace(/_/g, " ")}</span>
                <span className="play-ts">{Math.floor(c.timestamp / 60)}:{String(Math.floor(c.timestamp % 60)).padStart(2, "0")}</span>
                <span className="play-conf">{Math.round(c.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default memo(HighlightReel);
