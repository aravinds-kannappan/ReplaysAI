import { useEffect, useMemo, useRef, useState } from "react";
import { sampleTrack, type Annotation, type BallKeyframe, type PlayerKeyframe, type PlaySchema } from "../lib/playSchema";

type Score = { away: number; home: number };

export const AGENT_COLOR: Record<string, string> = {
  Scout: "#3b82f6", Stat: "#22c55e", Ref: "#f59e0b", Predict: "#06b6d4",
};

const lerpKf = (a: PlayerKeyframe, b: PlayerKeyframe, f: number): PlayerKeyframe => ({ t: 0, x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f });
const lerpBall = (a: BallKeyframe, b: BallKeyframe, f: number): BallKeyframe => ({ t: 0, x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, z: (a.z ?? 0) + ((b.z ?? 0) - (a.z ?? 0)) * f });

function Marker({ x, y, team, role, label }: { x: number; y: number; team: string; role: string; label?: string }) {
  const ball = role === "ball";
  const cls = `pa-marker ${team === "off" ? "pa-off" : "pa-def"} ${ball ? "pa-ball-carrier" : ""}`;
  return (
    <g className={cls} style={{ transform: `translate(${x}px, ${y}px)` }}>
      {ball && <circle className="pa-ring" cx="0" cy="0" r="2.8" />}
      <ellipse className="pa-body" cx="0" cy="0.9" rx="1.25" ry="1.65" />
      <circle className="pa-head" cx="0" cy="-1.1" r="0.95" />
      {label && <text className="pa-label" x="0" y="4.3">{label}</text>}
    </g>
  );
}

function FieldSurface({ los, goal }: { los: number; goal: number }) {
  return (
    <>
      <rect x="0" y="0" width="100" height="60" className="pa-turf field" />
      {[10, 22, 34, 46, 58, 70].map((x) => <line key={x} x1={x} y1="3" x2={x} y2="57" className="pa-yard" />)}
      {[10, 22, 34, 46, 58, 70].map((x) => [24, 36].map((y) => <line key={`${x}-${y}`} x1={x - 1} y1={y} x2={x + 1} y2={y} className="pa-hash" />))}
      <rect x="88" y="0" width="12" height="60" className="pa-ez" />
      <line x1="88" y1="0" x2="88" y2="60" className="pa-goal" />
      <line x1={los} y1="2" x2={los} y2="58" className="pa-los" />
      <g className="pa-uprights">
        <line x1={goal} y1="20" x2={goal} y2="40" /><line x1={goal} y1="20" x2={goal + 2.5} y2="20" />
        <line x1={goal} y1="40" x2={goal + 2.5} y2="40" /><line x1={goal} y1="30" x2={goal - 2} y2="30" />
      </g>
    </>
  );
}

function CourtSurface({ goal }: { goal: number }) {
  return (
    <>
      <rect x="0" y="0" width="100" height="60" className="pa-turf court" />
      <rect x="2" y="2" width="96" height="56" className="pa-court-bound" />
      <line x1="6" y1="2" x2="6" y2="58" className="pa-court-line" />
      <circle cx="6" cy="30" r="7" className="pa-court-line" />
      {/* paint + hoop on the right */}
      <rect x={goal - 16} y="20" width="16" height="20" className="pa-paint" />
      <path d={`M ${goal - 16} 20 A 12 12 0 0 1 ${goal - 16} 40`} className="pa-court-line" />
      <path d={`M ${goal} 8 A 26 26 0 0 0 ${goal} 52`} className="pa-arc" />
      <line x1={goal} y1="8" x2={goal} y2="52" className="pa-court-line" />
      <circle cx={goal - 2} cy="30" r="1.6" className="pa-rim" />
    </>
  );
}

export default function PlayAnimation({
  schema, awayAbbr, homeAbbr, scoreBefore, scoreAfter, annotations = [], compact = false, loop = false,
}: {
  schema: PlaySchema; awayAbbr: string; homeAbbr: string; scoreBefore: Score; scoreAfter: Score;
  annotations?: Annotation[]; compact?: boolean; loop?: boolean;
}) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(true);
  const raf = useRef(0);
  const startRef = useRef(0);

  useEffect(() => {
    if (!playing) return;
    startRef.current = performance.now() - t * schema.durationMs;
    const step = (now: number) => {
      let nt = (now - startRef.current) / schema.durationMs;
      if (nt >= 1) {
        if (loop) { startRef.current = now + 600; nt = 0; }   // brief pause then loop
        else { setT(1); setPlaying(false); return; }
      }
      setT(Math.max(0, Math.min(1, nt)));
      raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, schema, loop]);

  function replay() { setT(0); setPlaying(true); }
  function toggle() { if (t >= 1 && !loop) { replay(); return; } setPlaying((p) => !p); }

  const players = useMemo(() => schema.players.map((p) => ({ ...p, pos: sampleTrack(p.keyframes, t, lerpKf) })), [schema, t]);
  const ball = sampleTrack(schema.ballKeyframes, t, lerpBall);
  const z = ball.z ?? 0;
  const scoreEventT = schema.events.find((e) => e.type === "score")?.t ?? 0.9;
  const score = t >= scoreEventT ? scoreAfter : scoreBefore;
  const activeEvent = [...schema.events].reverse().find((e) => t >= e.t && t <= e.t + 0.12);
  const lit = schema.events.some((e) => (e.type === "through" || e.type === "score") && t >= e.t && schema.result === "score") || (schema.result === "good" && schema.events.some((e) => e.type === "through" && t >= e.t));
  const liftY = schema.surface === "court" ? 7 : 9;
  const activeAnns = annotations.filter((a) => t >= a.t && t <= a.t + 0.28);

  return (
    <div className={`pa-wrap ${compact ? "pa-compact" : ""}`}>
      {!compact && (
        <div className="pa-scorebar">
          <span className={score.away >= score.home ? "lead" : ""}><b>{awayAbbr}</b> {score.away}</span>
          <span className="pa-clock">{schema.kind.replace(/_/g, " ").toUpperCase()}</span>
          <span className={score.home >= score.away ? "lead" : ""}>{score.home} <b>{homeAbbr}</b></span>
        </div>
      )}

      <div className="pa-stage">
        <svg className="pa-field" viewBox="0 0 100 60" preserveAspectRatio="xMidYMid meet">
          {schema.surface === "court" ? <CourtSurface goal={schema.goal} /> : <FieldSurface los={schema.los} goal={schema.goal} />}
          <g className={lit ? "pa-goalzone lit" : "pa-goalzone"} />
          {players.map((p) => <Marker key={p.id} x={p.pos.x} y={p.pos.y} team={p.team} role={p.role} label={p.label} />)}
          <ellipse className="pa-ball-shadow" cx={ball.x} cy={ball.y} rx={1.1 - z * 0.4} ry={0.5 - z * 0.18} />
          <ellipse className={`pa-ball ${schema.surface}`} cx={ball.x} cy={ball.y - z * liftY} rx="1.1" ry={schema.surface === "court" ? 1.1 : 0.8} />
        </svg>

        {/* agent pop-ups */}
        <div className="pa-anns">
          {activeAnns.map((a, i) => (
            <div key={`${a.agent}-${a.t}-${i}`} className="pa-ann" style={{ ["--c" as string]: AGENT_COLOR[a.agent] || "#8b99b3" }}>
              <b>{a.agent}</b><span>{a.text}</span>
            </div>
          ))}
        </div>
        {activeEvent?.label && <span className={`pa-event ev-${activeEvent.type}`}>{activeEvent.label}</span>}
      </div>

      {!compact && (
        <div className="pa-controls">
          <div className="pa-timeline"><i style={{ width: `${t * 100}%` }} /></div>
          <button className="pa-btn" onClick={toggle}>{t >= 1 && !loop ? "↺" : playing ? "⏸" : "▶"}</button>
        </div>
      )}
    </div>
  );
}
