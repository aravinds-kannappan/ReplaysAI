import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";

export type Clip = {
  id: string;
  headline: string;
  description: string;
  duration: number;
  url: string;
  thumbnail: string;
  narration?: string;
};

export type Playlist = { label: string; clips: Clip[] };

/** Speak narration with the browser's voice. Returns a cancel fn. */
function narrate(text: string, onEnd?: () => void): () => void {
  if (typeof window === "undefined" || !window.speechSynthesis || !text) {
    onEnd?.();
    return () => undefined;
  }
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 1.03;
  if (onEnd) utter.onend = onEnd;
  window.speechSynthesis.speak(utter);
  return () => window.speechSynthesis.cancel();
}

function ClipVideo({ clip, voiceOn, onEnded }: { clip: Clip; voiceOn: boolean; onEnded: () => void }) {
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

  // Voice the narration over the clip, ducking the clip's own audio underneath.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const text = clip.narration || clip.headline;
    if (!voiceOn || !text) {
      video.muted = false;
      video.volume = 1;
      return;
    }
    video.muted = false;
    video.volume = 0.1;
    const cancel = narrate(text, () => {
      if (videoRef.current) videoRef.current.volume = 1;
    });
    return cancel;
  }, [clip.url, clip.narration, clip.headline, voiceOn]);

  return (
    <div className="clip-stage">
      <video ref={videoRef} poster={clip.thumbnail || undefined} controls autoPlay playsInline onEnded={onEnded} />
      {(clip.narration || clip.headline) && (
        <div className="clip-caption">{voiceOn ? "🔊 " : ""}{clip.narration || clip.headline}</div>
      )}
    </div>
  );
}

export default function ReelPlayer({ playlist, onClose }: { playlist: Playlist; onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const [voiceOn, setVoiceOn] = useState(true);
  const clip = playlist.clips[index];
  const totalSeconds = playlist.clips.reduce((sum, item) => sum + (item.duration || 0), 0);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  if (!clip) return null;

  return (
    <div className="reel-player">
      <div className="reel-player-head">
        <div>
          <strong>{playlist.label}</strong>
          <span>Clip {index + 1} of {playlist.clips.length} · ~{Math.max(1, Math.round(totalSeconds / 60))} min · narrated</span>
        </div>
        <div className="reel-player-head-btns">
          <button className={`btn-ghost ${voiceOn ? "voice-on" : ""}`} onClick={() => { setVoiceOn((v) => !v); window.speechSynthesis?.cancel(); }}>
            {voiceOn ? "🔊 Voice on" : "🔇 Voice off"}
          </button>
          <button className="btn-ghost" onClick={() => { window.speechSynthesis?.cancel(); onClose(); }}>Close</button>
        </div>
      </div>
      <ClipVideo
        key={clip.url}
        clip={clip}
        voiceOn={voiceOn}
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
