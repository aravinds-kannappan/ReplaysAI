import { useEffect, useMemo, useRef, useState } from "react";
import { sampleTrack, type BallKeyframe, type PlayerKeyframe, type PlaySchema } from "../lib/playSchema";

type Score = { away: number; home: number };

const lerpKf = (a: PlayerKeyframe, b: PlayerKeyframe, f: number): PlayerKeyframe => ({
  t: 0, x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f,
});
const lerpBall = (a: BallKeyframe, b: BallKeyframe, f: number): BallKeyframe => ({
  t: 0, x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, z: (a.z ?? 0) + ((b.z ?? 0) - (a.z ?? 0)) * f,
});

function Marker({ x, y, team, role, label }: { x: number; y: number; team: string; role: string; label: string }) {
  const star = role === "K" || role === "H" || role === "LS";
  const cls = `pa-marker ${team === "kick" ? "pa-kick" : "pa-def"} ${star ? "pa-star" : ""}`;
  return (
    <g className={cls} style={{ transform: `translate(${x}px, ${y}px)` }}>
      <ellipse className="pa-body" cx="0" cy="0.9" rx="1.3" ry="1.7" />
      <circle className="pa-head" cx="0" cy="-1.1" r="1" />
      <text className="pa-label" x="0" y="4.4">{label}</text>
    </g>
  );
}

export default function FootballPlayAnimation({
  schema, awayAbbr, homeAbbr, scoreBefore, scoreAfter,
}: {
  schema: PlaySchema; awayAbbr: string; homeAbbr: string; scoreBefore: Score; scoreAfter: Score;
}) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(true);
  const raf = useRef(0);
  const startRef = useRef(0);

  useEffect(() => {
    if (!playing) return;
    startRef.current = performance.now() - t * schema.durationMs;
    const step = (now: number) => {
      const nt = Math.min(1, (now - startRef.current) / schema.durationMs);
      setT(nt);
      if (nt < 1) raf.current = requestAnimationFrame(step);
      else setPlaying(false);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, schema]);

  function replay() { setT(0); setPlaying(true); }
  function toggle() { if (t >= 1) { replay(); return; } setPlaying((p) => !p); }

  const players = useMemo(
    () => schema.players.map((p) => ({ ...p, pos: sampleTrack(p.keyframes, t, lerpKf) })),
    [schema, t],
  );
  const ball = sampleTrack(schema.ballKeyframes, t, lerpBall);
  const z = ball.z ?? 0;

  const scoreEventT = schema.events.find((e) => e.type === "score")?.t ?? 0.9;
  const score = t >= scoreEventT ? scoreAfter : scoreBefore;
  const activeEvent = [...schema.events].reverse().find((e) => t >= e.t && t <= e.t + 0.12);
  const uprightLit = schema.events.some((e) => (e.type === "through" || e.type === "score") && t >= e.t && schema.result === "good");

  return (
    <div className="pa-wrap">
      <div className="pa-scorebar">
        <span className={score.away >= score.home ? "lead" : ""}><b>{awayAbbr}</b> {score.away}</span>
        <span className="pa-clock">{schema.kind === "field_goal" ? "FIELD GOAL" : schema.kind.toUpperCase()}</span>
        <span className={score.home >= score.away ? "lead" : ""}>{score.home} <b>{homeAbbr}</b></span>
      </div>

      <svg className="pa-field" viewBox="0 0 100 60" preserveAspectRatio="xMidYMid meet">
        {/* turf + yard lines */}
        <rect x="0" y="0" width="100" height="60" className="pa-turf" />
        {[10, 22, 34, 46, 58, 70].map((x) => <line key={x} x1={x} y1="3" x2={x} y2="57" className="pa-yard" />)}
        {/* hash marks */}
        {[10, 22, 34, 46, 58, 70].map((x) => [24, 36].map((y) => <line key={`${x}-${y}`} x1={x - 1} y1={y} x2={x + 1} y2={y} className="pa-hash" />))}
        {/* end zone + goal line */}
        <rect x="88" y="0" width="12" height="60" className="pa-ez" />
        <line x1="88" y1="0" x2="88" y2="60" className="pa-goal" />
        {/* line of scrimmage */}
        <line x1={schema.los} y1="2" x2={schema.los} y2="58" className="pa-los" />
        {/* uprights (goal posts) */}
        <g className={`pa-uprights ${uprightLit ? "lit" : ""}`}>
          <line x1={schema.uprights} y1="20" x2={schema.uprights} y2="40" />
          <line x1={schema.uprights} y1="20" x2={schema.uprights + 2.5} y2="20" />
          <line x1={schema.uprights} y1="40" x2={schema.uprights + 2.5} y2="40" />
          <line x1={schema.uprights} y1="30" x2={schema.uprights - 2} y2="30" />
        </g>

        {/* players */}
        {players.map((p) => <Marker key={p.id} x={p.pos.x} y={p.pos.y} team={p.team} role={p.role} label={p.label} />)}

        {/* ball: shadow on the turf, ball raised by its height z */}
        <ellipse className="pa-ball-shadow" cx={ball.x} cy={ball.y} rx={1.1 - z * 0.4} ry={0.5 - z * 0.18} />
        <ellipse className="pa-ball" cx={ball.x} cy={ball.y - z * 9} rx="1.1" ry="0.8" />
      </svg>

      <div className="pa-controls">
        <div className="pa-timeline"><i style={{ width: `${t * 100}%` }} /></div>
        <button className="pa-btn" onClick={toggle}>{t >= 1 ? "↺ Replay" : playing ? "⏸" : "▶"}</button>
        {activeEvent?.label && <span className={`pa-event ev-${activeEvent.type}`}>{activeEvent.label}</span>}
      </div>
    </div>
  );
}
