import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import KeyPlayModal, { type PlayFacts, type PlayAnalysis, type KeyPlay } from "./KeyPlayModal";
import PlayAnimation from "./PlayAnimation";
import { buildPlaySchema } from "../lib/playSchema";
import { agentAnnotations } from "../lib/agentAnnotations";

export type StoryScene = {
  type: "title" | "moment" | "run" | "break" | "stat" | "verdict";
  duration: number;
  heading?: string;
  text?: string;
  narration?: string;
  period?: number;
  clock?: string | null;
  score?: { away: number | null; home: number | null };
  play_type?: string;
  stats?: { label: string; value: string }[];
  play?: PlayFacts;
  analysis?: PlayAnalysis;
};

export type Story = {
  title: string;
  focus: string;
  duration_seconds: number;
  scene_count: number;
  scenes: StoryScene[];
  generated_by?: string;
  sport?: string;
  away_abbr?: string;
  home_abbr?: string;
};

/* ── Most natural English voice available ── */
function pickVoice(): SpeechSynthesisVoice | null {
  const all = window.speechSynthesis?.getVoices() ?? [];
  const en = all.filter((v) => v.lang.toLowerCase().startsWith("en"));
  if (!en.length) return null;
  const prefer = ["Google US English", "Microsoft Aria", "Microsoft Jenny", "Samantha", "Microsoft Guy", "Daniel", "Alex"];
  for (const name of prefer) {
    const v = en.find((x) => x.name.includes(name));
    if (v) return v;
  }
  return en.find((v) => /natural|neural|enhanced|premium|siri/i.test(v.name)) ?? en.find((v) => v.localService === false) ?? en[0];
}

/* ── Tweened scoreboard number (counts up as the game's score climbs) ── */
function useTweenedNumber(target: number | null): number | null {
  const [value, setValue] = useState<number | null>(target);
  const fromRef = useRef<number | null>(target);
  useEffect(() => {
    const from = fromRef.current;
    if (target === null || from === null || from === target) { fromRef.current = target; setValue(target); return; }
    const start = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / 650);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (t < 1) raf = requestAnimationFrame(step);
      else fromRef.current = target;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return value;
}

function Scoreboard({ scene, awayAbbr, homeAbbr }: { scene: StoryScene; awayAbbr: string; homeAbbr: string }) {
  const away = useTweenedNumber(scene.score?.away ?? null);
  const home = useTweenedNumber(scene.score?.home ?? null);
  if (away === null || home === null) return null;
  return (
    <div className="sr-score">
      <div className={`sr-score-team ${away >= home ? "lead" : ""}`}><span>{awayAbbr}</span><b>{away}</b></div>
      <i>–</i>
      <div className={`sr-score-team ${home >= away ? "lead" : ""}`}><span>{homeAbbr}</span><b>{home}</b></div>
    </div>
  );
}

/* ── Inline animated play for a reel moment scene ── */
function MomentPlay({ scene, sport, away, home }: { scene: StoryScene; sport?: string; away: string; home: string }) {
  const schema = useMemo(() => buildPlaySchema({
    sport: sport || "NFL",
    playType: scene.play?.play_type || scene.play_type || "",
    description: scene.play?.description || scene.text || "",
    fgDistance: scene.play?.fg_distance ?? null,
    yardsToGoal: scene.play?.yards_to_goal ?? null,
    offAbbr: scene.play?.kicking_team || away,
    defAbbr: scene.play?.kicking_team === away ? home : away,
  }), [scene, sport, away, home]);
  const annotations = useMemo(() => agentAnnotations(scene.analysis?.agents || []), [scene.analysis]);
  return (
    <PlayAnimation
      schema={schema}
      awayAbbr={away}
      homeAbbr={home}
      annotations={annotations}
      compact loop
      scoreBefore={{ away: scene.play?.prev_away ?? 0, home: scene.play?.prev_home ?? 0 }}
      scoreAfter={{ away: scene.play?.away_score ?? 0, home: scene.play?.home_score ?? 0 }}
    />
  );
}

const SCENE_KICKER: Record<StoryScene["type"], string> = {
  title: "The story", moment: "Key play", run: "Momentum", break: "Chapter", stat: "Who decided it", verdict: "Final",
};

export default function StoryReelPlayer({
  story, awayAbbr, homeAbbr, onClose,
}: {
  story: Story; awayAbbr: string; homeAbbr: string; onClose: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [muted, setMuted] = useState(false);
  const [done, setDone] = useState(false);
  const [breakdown, setBreakdown] = useState<KeyPlay | null>(null);
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const advancedRef = useRef(-1);
  const scene = story.scenes[index];
  const away = story.away_abbr || awayAbbr;
  const home = story.home_abbr || homeAbbr;

  function openBreakdown() {
    if (!scene?.play || !scene?.analysis) return;
    window.speechSynthesis?.cancel();
    setPlaying(false);
    setBreakdown({ play: scene.play, analysis: scene.analysis, awayAbbr: away, homeAbbr: home, sport: story.sport || "NFL", heading: scene.heading });
  }

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const set = () => { voiceRef.current = pickVoice(); };
    set();
    window.speechSynthesis.addEventListener?.("voiceschanged", set);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", set);
  }, []);

  const advance = useCallback(() => {
    if (advancedRef.current === index) return; // guard speech-end + safety timer double-fire
    advancedRef.current = index;
    if (index >= story.scenes.length - 1) { setPlaying(false); setDone(true); }
    else setIndex((i) => i + 1);
  }, [index, story.scenes.length]);

  // Speak the scene's narration and advance when it finishes (or on a timeout).
  useEffect(() => {
    if (!playing || done || !scene) return;
    advancedRef.current = -1;
    const synth = typeof window !== "undefined" ? window.speechSynthesis : null;
    const durMs = Math.max(2600, scene.duration * 1000);
    // Moment scenes hold for their full duration so the embedded play animation
    // plays out; other scenes advance as soon as the narration finishes.
    const isMoment = scene.type === "moment";
    if (synth && !muted && scene.narration) {
      synth.cancel();
      const utter = new SpeechSynthesisUtterance(scene.narration);
      if (voiceRef.current) utter.voice = voiceRef.current;
      utter.rate = 0.98;
      if (!isMoment) utter.onend = () => advance();
      const start = window.setTimeout(() => synth.speak(utter), 120);
      const timer = window.setTimeout(advance, isMoment ? durMs : durMs + 4500);
      return () => { window.clearTimeout(start); window.clearTimeout(timer); synth.cancel(); };
    }
    const timer = window.setTimeout(advance, durMs);
    return () => window.clearTimeout(timer);
  }, [index, playing, muted, done, scene, advance]);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  if (!scene) return null;

  function jump(to: number) {
    window.speechSynthesis?.cancel();
    advancedRef.current = -1;
    setIndex(Math.max(0, Math.min(to, story.scenes.length - 1)));
    setDone(false);
    setPlaying(true);
  }
  function togglePlay() {
    if (done) { jump(0); return; }
    if (playing) { window.speechSynthesis?.cancel(); setPlaying(false); }
    else { advancedRef.current = -1; setPlaying(true); }
  }
  function close() { window.speechSynthesis?.cancel(); onClose(); }

  return (
    <>
    {breakdown && <KeyPlayModal data={breakdown} onClose={() => setBreakdown(null)} />}
    <div className="sr-overlay" role="dialog" aria-label="Story reel">
      <div className={`sr-reel scene-${scene.type}`}>
        <div className="sr-progress">
          {story.scenes.map((s, i) => (
            <span key={i} onClick={() => jump(i)}>
              <i className={i < index ? "full" : ""} style={i === index ? { animation: `srFill ${s.duration}s linear forwards` } : undefined} />
            </span>
          ))}
        </div>

        <div className="sr-topbar">
          <span className="sr-kicker">🎬 {SCENE_KICKER[scene.type]}</span>
          <div className="sr-topbar-btns">
            <button onClick={() => { setMuted((m) => !m); window.speechSynthesis?.cancel(); advancedRef.current = -1; }}>{muted ? "🔇" : "🔊"}</button>
            <button onClick={close}>✕</button>
          </div>
        </div>

        <div className="sr-stage" onClick={togglePlay}>
          <div className="sr-bg" />
          {/* Persistent across scenes so the scoreboard tweens upward as the game's score climbs. */}
          <Scoreboard scene={scene} awayAbbr={away} homeAbbr={home} />

          <div className="sr-scene" key={index}>
            {scene.heading && <div className="sr-heading">{scene.heading}</div>}

            {scene.type === "moment" && scene.play && (
              <MomentPlay scene={scene} sport={story.sport} away={away} home={home} />
            )}
            {scene.type === "moment" && scene.play && scene.analysis && (
              <button className="sr-breakdown" onClick={(e) => { e.stopPropagation(); openBreakdown(); }}>
                🔬 Full breakdown & agents
              </button>
            )}

            {scene.type === "stat" && scene.stats ? (
              <div className="sr-stats">
                {scene.stats.map((row, i) => (
                  <div key={row.label} className="sr-stat" style={{ animationDelay: `${i * 0.14}s` }}>
                    <span className="sr-stat-name">{row.label}</span>
                    <b className="sr-stat-val">{row.value}</b>
                  </div>
                ))}
              </div>
            ) : (
              scene.text && <div className={`sr-text ${scene.type === "title" || scene.type === "verdict" ? "big" : ""}`}>{scene.text}</div>
            )}
          </div>

          {scene.narration && <p className="sr-narration" key={`n${index}`}>{scene.narration}</p>}
          {!playing && !done && <div className="sr-paused">tap to resume</div>}
        </div>

        <div className="sr-controls">
          <button className="btn-ghost" disabled={index === 0} onClick={() => jump(index - 1)}>‹</button>
          <button className="sr-play" onClick={togglePlay}>{done ? "↺ Replay" : playing ? "⏸ Pause" : "▶ Play"}</button>
          <button className="btn-ghost" disabled={index >= story.scenes.length - 1} onClick={() => jump(index + 1)}>›</button>
          <span className="sr-count">{index + 1}/{story.scenes.length}{story.generated_by === "llm" ? " · AI-written" : ""}</span>
        </div>
      </div>
    </div>
    </>
  );
}
