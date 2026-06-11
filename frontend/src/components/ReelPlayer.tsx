import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";

export type Clip = {
  id: string;
  headline: string;
  description: string;
  duration: number;
  url: string;
  thumbnail: string;
};

export type Playlist = { label: string; clips: Clip[] };

function ClipVideo({ clip, onEnded }: { clip: Clip; onEnded: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const isHlsUrl = clip.url.includes(".m3u8");
    if (isHlsUrl && !video.canPlayType("application/vnd.apple.mpegurl") && Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(clip.url);
      hls.attachMedia(video);
      return () => hls.destroy();
    }
    video.src = clip.url; // Safari plays HLS natively; MP4s play everywhere
  }, [clip.url]);

  return (
    <video
      ref={videoRef}
      poster={clip.thumbnail || undefined}
      controls
      autoPlay
      playsInline
      onEnded={onEnded}
    />
  );
}

export default function ReelPlayer({ playlist, onClose }: { playlist: Playlist; onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const clip = playlist.clips[index];
  const totalSeconds = playlist.clips.reduce((sum, item) => sum + (item.duration || 0), 0);
  if (!clip) return null;

  return (
    <div className="reel-player">
      <div className="reel-player-head">
        <div>
          <strong>{playlist.label}</strong>
          <span>Clip {index + 1} of {playlist.clips.length} · ~{Math.max(1, Math.round(totalSeconds / 60))} min total</span>
        </div>
        <button className="btn-ghost" onClick={onClose}>Close</button>
      </div>
      <ClipVideo
        key={clip.url}
        clip={clip}
        onEnded={() => setIndex((i) => Math.min(i + 1, playlist.clips.length - 1))}
      />
      <div className="reel-player-meta">
        <strong>{clip.headline}</strong>
        <div className="reel-player-nav">
          <button className="btn-ghost" disabled={index === 0} onClick={() => setIndex(index - 1)}>Prev</button>
          <button className="btn-ghost" disabled={index === playlist.clips.length - 1} onClick={() => setIndex(index + 1)}>Next</button>
        </div>
      </div>
    </div>
  );
}
