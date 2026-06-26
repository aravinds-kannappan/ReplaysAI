import { useCallback, useEffect, useRef, useState } from "react";

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

/* ── Sport-aware play animation ── */
function PlayViz({ playType, sport }: { playType?: string; sport?: string }) {
  const isNFL = (sport || "").toUpperCase() === "NFL";
  const reverse = ["interception", "turnover", "steal", "block", "fumble"].includes(playType || "");
  if (isNFL) {
    const d = reverse ? "M 210 60 Q 120 20 26 64" : "M 26 64 Q 130 6 214 58";
    return (
      <svg className="sr-field" viewBox="0 0 240 120" aria-hidden="true">
        <rect x="0" y="0" width="240" height="120" className="fld-grass" />
        {[40, 80, 120, 160, 200].map((x) => <line key={x} x1={x} y1="6" x2={x} y2="114" className="fld-line" />)}
        <rect x="0" y="0" width="22" height="120" className="fld-ez" />
        <rect x="218" y="0" width="22" height="120" className="fld-ez" />
        <path id="srpath" d={d} className="fld-path" />
        <g className="fld-ball">
          <ellipse rx="6" ry="4" />
          <animateMotion dur="2.2s" repeatCount="indefinite" rotate="auto" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.4 0 0.2 1">
            <mpath href="#srpath" />
          </animateMotion>
        </g>
      </svg>
    );
  }
  const arc = playType === "three_pointer";
  const d = reverse ? "M 222 60 Q 120 96 26 38" : arc ? "M 30 96 Q 130 -20 220 56" : "M 28 80 Q 140 78 218 60";
  return (
    <svg className="sr-court" viewBox="0 0 240 120" aria-hidden="true">
      <rect x="2" y="2" width="236" height="116" rx="10" className="crt-floor" />
      <path d="M 238 18 A 50 50 0 0 0 238 102" className="crt-line" />
      <circle cx="222" cy="60" r="5" className="crt-rim" />
      <path id="srpath" d={d} className="crt-path" />
      <g className="crt-ball">
        <circle r="6" />
        <animateMotion dur="2s" repeatCount="indefinite" calcMode="spline" keyPoints="0;1" keyTimes="0;1" keySplines="0.4 0 0.2 1">
          <mpath href="#srpath" />
        </animateMotion>
      </g>
    </svg>
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
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const advancedRef = useRef(-1);
  const scene = story.scenes[index];
  const away = story.away_abbr || awayAbbr;
  const home = story.home_abbr || homeAbbr;

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
    if (synth && !muted && scene.narration) {
      synth.cancel();
      const utter = new SpeechSynthesisUtterance(scene.narration);
      if (voiceRef.current) utter.voice = voiceRef.current;
      utter.rate = 0.98;
      utter.onend = () => advance();
      const start = window.setTimeout(() => synth.speak(utter), 120);
      const safety = window.setTimeout(advance, durMs + 4500); // if onend never fires
      return () => { window.clearTimeout(start); window.clearTimeout(safety); synth.cancel(); };
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

            {scene.type === "moment" && <PlayViz playType={scene.play_type} sport={story.sport} />}

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
          <span className="sr-count">{index + 1}/{story.scenes.length}{story.generated_by === "llm" ? " · AI" : ""}</span>
        </div>
      </div>
    </div>
  );
}
