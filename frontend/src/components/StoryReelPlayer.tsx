import { useEffect, useRef, useState } from "react";

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
};

const TICK_MS = 100;

function useTweenedNumber(target: number | null): number | null {
  const [value, setValue] = useState<number | null>(target);
  const fromRef = useRef<number | null>(target);

  useEffect(() => {
    const from = fromRef.current;
    if (target === null || from === null || from === target) {
      fromRef.current = target;
      setValue(target);
      return;
    }
    const start = performance.now();
    const ms = 700;
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      setValue(Math.round(from + (target - from) * t));
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
    <div className="story-scoreboard">
      <span className={away >= home ? "leading" : ""}><b>{awayAbbr}</b> {away}</span>
      <i>—</i>
      <span className={home >= away ? "leading" : ""}>{home} <b>{homeAbbr}</b></span>
    </div>
  );
}

// Stylized possession animation — a ball travelling a path chosen by play type.
function PossessionViz({ playType }: { playType?: string }) {
  const kind =
    playType === "three_pointer" ? "arc-deep"
    : playType === "dunk" || playType === "shot" || playType === "touchdown" ? "drive"
    : playType === "block" || playType === "steal" || playType === "interception" || playType === "turnover" ? "reverse"
    : "drive";
  return (
    <svg className="story-court" viewBox="0 0 200 90" aria-hidden="true">
      <rect x="2" y="2" width="196" height="86" rx="8" className="court-floor" />
      <path d="M 198 10 A 55 55 0 0 0 198 80" className="court-line" />
      <circle cx="184" cy="45" r="4" className="court-rim" />
      <path
        d={
          kind === "arc-deep" ? "M 30 70 Q 110 -18 184 41"
          : kind === "reverse" ? "M 184 45 Q 100 70 24 30"
          : "M 24 60 Q 120 58 182 47"
        }
        className="court-path"
      />
      <circle r="5" className={`court-ball ball-${kind}`} />
    </svg>
  );
}

const SCENE_KICKER: Record<StoryScene["type"], string> = {
  title: "Tonight's story",
  moment: "Key moment",
  run: "Momentum swing",
  break: "Chapter",
  stat: "By the numbers",
  verdict: "The verdict",
};

export default function StoryReelPlayer({
  story,
  awayAbbr,
  homeAbbr,
  onClose,
}: {
  story: Story;
  awayAbbr: string;
  homeAbbr: string;
  onClose: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(true);
  const scene = story.scenes[index];
  const done = index >= story.scenes.length - 1 && scene && elapsed >= scene.duration;

  useEffect(() => {
    if (!playing || !scene || done) return;
    const timer = setInterval(() => {
      setElapsed((prev) => {
        const next = prev + TICK_MS / 1000;
        if (next >= scene.duration) {
          setIndex((i) => Math.min(i + 1, story.scenes.length - 1));
          return index >= story.scenes.length - 1 ? scene.duration : 0;
        }
        return next;
      });
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [playing, scene, index, story.scenes.length, done]);

  if (!scene) return null;

  function jump(to: number) {
    setIndex(Math.max(0, Math.min(to, story.scenes.length - 1)));
    setElapsed(0);
    setPlaying(true);
  }

  return (
    <div className={`story-player scene-${scene.type}`}>
      <div className="story-progress">
        {story.scenes.map((s, i) => (
          <span key={i} onClick={() => jump(i)}>
            <i
              style={{
                width:
                  i < index ? "100%" : i === index ? `${Math.min(100, (elapsed / s.duration) * 100)}%` : "0%",
              }}
            />
          </span>
        ))}
      </div>

      <div className="story-top">
        <div>
          <span className="story-kicker">{SCENE_KICKER[scene.type]}</span>
          <strong>{story.title}</strong>
        </div>
        <button className="btn-ghost" onClick={onClose}>Close</button>
      </div>

      <div className="story-stage" key={index} onClick={() => setPlaying((p) => !p)}>
        {scene.heading && <div className="story-heading">{scene.heading}</div>}
        <Scoreboard scene={scene} awayAbbr={awayAbbr} homeAbbr={homeAbbr} />

        {scene.type === "moment" && <PossessionViz playType={scene.play_type} />}

        {scene.type === "stat" && scene.stats ? (
          <div className="story-stats">
            {scene.stats.map((row, i) => (
              <div key={row.label} className="story-stat-row" style={{ animationDelay: `${i * 0.12}s` }}>
                <span>{row.label}</span>
                <b>{row.value}</b>
              </div>
            ))}
          </div>
        ) : (
          scene.text && <div className={`story-text ${scene.type === "title" || scene.type === "verdict" ? "big" : ""}`}>{scene.text}</div>
        )}

        {scene.narration && <p className="story-narration">{scene.narration}</p>}
        {!playing && <div className="story-paused">paused — tap to resume</div>}
      </div>

      <div className="story-controls">
        <button className="btn-ghost" disabled={index === 0} onClick={() => jump(index - 1)}>‹ Prev</button>
        <button className="btn-ghost" onClick={() => setPlaying((p) => !p)}>{playing && !done ? "Pause" : done ? "Done" : "Play"}</button>
        <button className="btn-ghost" disabled={index >= story.scenes.length - 1} onClick={() => jump(index + 1)}>Next ›</button>
        <span className="story-meta">
          scene {index + 1}/{story.scenes.length} · ~{Math.max(1, Math.round(story.duration_seconds / 60))} min
          {story.generated_by === "llm" ? " · AI-narrated" : ""}
        </span>
      </div>
    </div>
  );
}
