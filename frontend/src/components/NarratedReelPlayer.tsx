import { useEffect, useMemo, useRef, useState } from "react";
import Hls from "hls.js";
import type { Clip } from "./ReelPlayer";

export type NarratedReel = {
  label: string;       // tier label, e.g. "2 min story"
  gameLabel: string;   // "LAR @ CHI 20-17"
  script: string;      // the AI voice-over script
  clips: Clip[];       // optional b-roll (may be empty)
};

/* ── Script → speakable lines ──────────────────────────────────────────────
   The voice script can arrive as markdown with section headers and bracketed
   timing cues; strip those and split into sentence-sized lines so captions and
   speech advance together. */
function toLines(script: string, gameLabel: string): string[] {
  const raw = (script || "").replace(/```[\s\S]*?```/g, " ");
  const out: string[] = [];
  for (const rawLine of raw.split(/\n+/)) {
    const line = rawLine
      .replace(/^#{1,6}\s*/, "")              // markdown headers
      .replace(/\[[^\]]*\]/g, " ")             // bracketed cues e.g. [CLIP: …]
      .replace(/[*_>`]+/g, "")                 // emphasis markers
      .replace(/-{2,}/g, " ")                  // --- rules
      .replace(/\(\s*\d+\s*sec[^)]*\)/gi, " ") // "(120 SEC REEL)"
      .replace(/["'“”‘’]/g, "") // stray quotes
      .replace(/\s+/g, " ")
      .trim();
    if (line.length < 3) continue;
    // Skip production labels that shouldn't be read aloud: "CLIP 2:", "Scene 1 -", etc.
    if (/^(clip|scene|shot|segment|cut|title|intro|outro)\b[\s\d]*[:\-–]/i.test(line)) continue;
    // Drop short all-caps section labels (OPEN, CLIP-BY-CLIP SCRIPT, …) but keep
    // a title-length line as the opener.
    if (line.length <= 30 && line === line.toUpperCase() && !/[.!?]$/.test(line)) continue;
    const parts = line.match(/[^.!?]+[.!?]+|\S[^.!?]*$/g) ?? [line];
    for (const p of parts) {
      const s = p.trim();
      if (s.length > 2) out.push(s);
    }
  }
  if (out.length) return out;
  // Fallback so the reel always speaks something.
  return [
    `Here's the story of ${gameLabel || "this game"}.`,
    "A look at how it played out, possession by possession.",
    "That's the reel.",
  ];
}

/* Parse "LAR @ CHI 20-17" → scoreboard. */
function parseGame(label: string) {
  const m = label.match(/([A-Z]{2,4})\s*@\s*([A-Z]{2,4})\s*(\d+)?\s*-?\s*(\d+)?/);
  if (!m) return { away: "AWY", home: "HME", aScore: null as number | null, hScore: null as number | null };
  return { away: m[1], home: m[2], aScore: m[3] ? +m[3] : null, hScore: m[4] ? +m[4] : null };
}

/* ── Pick the most natural English voice available ── */
function pickVoice(): SpeechSynthesisVoice | null {
  const all = window.speechSynthesis?.getVoices() ?? [];
  const en = all.filter((v) => v.lang.toLowerCase().startsWith("en"));
  if (!en.length) return null;
  const prefer = [
    "Google US English", "Microsoft Aria", "Microsoft Jenny", "Samantha",
    "Microsoft Guy", "Google UK English Male", "Daniel", "Alex", "Karen",
  ];
  for (const name of prefer) {
    const v = en.find((x) => x.name.includes(name));
    if (v) return v;
  }
  const natural = en.find((v) => /natural|neural|enhanced|premium|siri/i.test(v.name));
  return natural ?? en.find((v) => v.localService === false) ?? en[0];
}

function BRoll({ clip }: { clip: Clip | undefined }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const video = ref.current;
    if (!video || !clip) return;
    video.muted = true;
    if (clip.url.includes(".m3u8") && !video.canPlayType("application/vnd.apple.mpegurl") && Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(clip.url);
      hls.attachMedia(video);
      return () => hls.destroy();
    }
    video.src = clip.url;
  }, [clip]);
  if (!clip) return null;
  return <video ref={ref} className="nr-broll" poster={clip.thumbnail || undefined} autoPlay loop muted playsInline />;
}

export default function NarratedReelPlayer({ reel, onClose }: { reel: NarratedReel; onClose: () => void }) {
  const lines = useMemo(() => toLines(reel.script, reel.gameLabel), [reel.script, reel.gameLabel]);
  const game = useMemo(() => parseGame(reel.gameLabel), [reel.gameLabel]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [done, setDone] = useState(false);
  const [muted, setMuted] = useState(false);
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);

  // Resolve the best voice (it may load asynchronously).
  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const set = () => { voiceRef.current = pickVoice(); };
    set();
    window.speechSynthesis.addEventListener?.("voiceschanged", set);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", set);
  }, []);

  // Speak the current line; advance on end. Pausing/closing cancels speech.
  useEffect(() => {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : null;
    if (!synth || !playing || muted) return;
    const line = lines[index];
    if (!line) return;
    synth.cancel();
    const utter = new SpeechSynthesisUtterance(line);
    if (voiceRef.current) utter.voice = voiceRef.current;
    utter.rate = 0.96;   // a touch slower reads more naturally
    utter.pitch = 1.0;
    utter.onend = () => {
      if (index < lines.length - 1) setIndex((i) => i + 1);
      else { setPlaying(false); setDone(true); }
    };
    // Brief beat between lines so it doesn't sound rushed.
    const t = window.setTimeout(() => synth.speak(utter), 160);
    return () => { window.clearTimeout(t); synth.cancel(); };
  }, [playing, muted, index, lines]);

  // When muted, still auto-advance captions on a timer so the reel plays through.
  useEffect(() => {
    if (!playing || !muted) return;
    const line = lines[index] || "";
    const ms = Math.max(2200, Math.min(7000, line.length * 55));
    const t = window.setTimeout(() => {
      if (index < lines.length - 1) setIndex((i) => i + 1);
      else { setPlaying(false); setDone(true); }
    }, ms);
    return () => window.clearTimeout(t);
  }, [playing, muted, index, lines]);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  // B-roll advances with the script.
  const clip = reel.clips.length ? reel.clips[index % reel.clips.length] : undefined;

  function restart() { window.speechSynthesis?.cancel(); setIndex(0); setDone(false); setPlaying(true); }
  function toggle() {
    if (done) { restart(); return; }
    if (playing) { window.speechSynthesis?.cancel(); setPlaying(false); }
    else { setPlaying(true); }
  }
  function close() { window.speechSynthesis?.cancel(); onClose(); }

  return (
    <div className="nr-overlay" role="dialog" aria-label="Narrated reel">
      <div className={`nr-player ${clip ? "has-broll" : "story"}`}>
        <header className="nr-head">
          <div>
            <span className="nr-kicker">🔊 Narrated reel · {reel.label}</span>
            <strong>{reel.gameLabel}</strong>
          </div>
          <div className="nr-head-btns">
            <button className="btn-ghost" onClick={() => { setMuted((m) => !m); window.speechSynthesis?.cancel(); }}>
              {muted ? "🔇 Voice off" : "🔊 Voice on"}
            </button>
            <button className="btn-ghost" onClick={close}>Close</button>
          </div>
        </header>

        <div className="nr-stage">
          <BRoll clip={clip} />
          <div className="nr-scrim" />
          <div className="nr-scoreboard">
            <span className="nr-team"><b>{game.away}</b>{game.aScore != null && <i>{game.aScore}</i>}</span>
            <span className="nr-sep">@</span>
            <span className="nr-team"><b>{game.home}</b>{game.hScore != null && <i>{game.hScore}</i>}</span>
          </div>
          <p className="nr-caption" key={index}>{lines[index]}</p>
          {done && <div className="nr-done">End of reel</div>}
        </div>

        <div className="nr-controls">
          <div className="nr-progress">
            {lines.map((_, i) => <span key={i} className={i <= index ? "on" : ""} />)}
          </div>
          <div className="nr-buttons">
            <button className="btn-ghost" disabled={index === 0} onClick={() => { window.speechSynthesis?.cancel(); setIndex((i) => Math.max(0, i - 1)); setDone(false); }}>‹ Prev</button>
            <button className="nr-play" onClick={toggle}>{done ? "↺ Replay" : playing ? "⏸ Pause" : "▶ Play"}</button>
            <button className="btn-ghost" disabled={index >= lines.length - 1} onClick={() => { window.speechSynthesis?.cancel(); setIndex((i) => Math.min(lines.length - 1, i + 1)); }}>Next ›</button>
          </div>
          <span className="nr-count">{index + 1} / {lines.length}</span>
        </div>
      </div>
    </div>
  );
}
