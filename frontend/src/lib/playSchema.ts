/* ──────────────────────────────────────────────────────────────────────────
   Play animation schema + generators (NFL field + NBA court).

   A play is declared as players (each with a start point and timed keyframes), a
   ball trajectory, discrete events, and optional agent annotations that pop up
   during playback. A renderer interpolates this over a normalized timeline
   t∈[0,1]. Coordinates use a 100 × 60 surface; the attacking goal/hoop is on the
   right (x≈90). Only ball-involved players are labelled — the rest are plain
   dots so the field doesn't get cluttered.
   ────────────────────────────────────────────────────────────────────────── */

export type Vec = { x: number; y: number };
export type PlayerKeyframe = { t: number; x: number; y: number };
export type Team = "off" | "def";

export type PlayerSpec = {
  id: string;
  team: Team;
  role: string;        // "ball" marks the current ball-carrier visual
  label?: string;      // only set for hero players
  start: Vec;
  keyframes: PlayerKeyframe[];
};

export type BallKeyframe = { t: number; x: number; y: number; z?: number };
export type PlayEvent = { t: number; type: string; label?: string };
export type Annotation = { t: number; agent: "Scout" | "Stat" | "Ref" | "Predict"; text: string };

export type PlaySchema = {
  surface: "field" | "court";
  kind: string;
  result: string;
  durationMs: number;
  los: number;
  goal: number;                 // x of uprights / hoop
  players: PlayerSpec[];
  ballKeyframes: BallKeyframe[];
  events: PlayEvent[];
  annotations: Annotation[];
};

export type PlayInput = {
  sport: string;
  playType: string;
  description: string;
  fgDistance?: number | null;
  yardsToGoal?: number | null;
  offAbbr: string;
  defAbbr: string;
};

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const kf = (t: number, x: number, y: number): PlayerKeyframe => ({ t, x, y });
const still = (id: string, team: Team, role: string, x: number, y: number, push = 0): PlayerSpec =>
  ({ id, team, role, start: { x, y }, keyframes: [kf(0, x, y), kf(0.55, x + push, y), kf(1, x + push, y)] });

function names(desc: string) {
  const lead = /^([A-Z][.\s][A-Za-z'.\-]+)/.exec(desc)?.[1]?.trim();
  const assist = /\(([A-Za-z'.\-\s]+?)\s+assists?\)/.exec(desc)?.[1]?.trim();
  const holder = /Holder-([A-Z]\.[A-Za-z'-]+)/.exec(desc)?.[1];
  const last = (n?: string) => n ? n.split(/\s+/).slice(-1)[0] : undefined;
  return { lead, assist, holder, leadLast: last(lead), assistLast: last(assist) };
}

/* ════════════════════ NFL ════════════════════ */
function fieldGoal(input: PlayInput): PlaySchema {
  const goal = 94, goalLine = 88;
  const ytg = clamp(input.yardsToGoal ?? (input.fgDistance ? input.fgDistance - 17 : 25), 3, 55);
  const los = clamp(goalLine - ytg * 1.25, 24, 76);
  const spot = los - 7.5;
  const n = names(input.description);
  const desc = input.description.toLowerCase();
  const result = desc.includes("blocked") ? "blocked" : (desc.includes("no good") || desc.includes("missed")) ? "miss" : "good";

  const players: PlayerSpec[] = [];
  players.push(still("ls", "off", "ol", los, 30, -0.6));
  [-9, -6, -3, 3, 6, 9].forEach((dy, i) => players.push(still(`ol${i}`, "off", "ol", los, 30 + dy, -0.5)));
  players.push(still("wl", "off", "ol", los, 13, -0.4), still("wr", "off", "ol", los, 47, -0.4));
  players.push({ id: "h", team: "off", role: "holder", label: n.holder || "Hold", start: { x: spot - 1.5, y: 30 }, keyframes: [kf(0, spot - 1.5, 30), kf(0.26, spot, 30), kf(1, spot, 30)] });
  players.push({ id: "k", team: "off", role: "ball", label: n.leadLast || "K", start: { x: spot - 4, y: 33.5 },
    keyframes: [kf(0, spot - 4, 33.5), kf(0.3, spot - 3, 32.5), kf(0.38, spot - 2.1, 31.6), kf(0.46, spot - 1.2, 30.6), kf(0.5, spot - 0.6, 30), kf(1, spot - 0.6, 30)] });
  const rush = (id: string, y: number) => ({ id, team: "def" as Team, role: "d", start: { x: los + 2.2, y }, keyframes: [kf(0, los + 2.2, y), kf(0.12, los + 2.2, y), kf(0.55, spot + 2.5, 30 + (y - 30) * 0.3), kf(1, spot + 2.5, 30 + (y - 30) * 0.3)] });
  [22, 26, 30, 34, 38].forEach((y, i) => players.push(rush(`r${i}`, y)));
  players.push({ id: "el", team: "def", role: "d", start: { x: los + 1.5, y: 12 }, keyframes: [kf(0, los + 1.5, 12), kf(0.55, spot + 4, 24), kf(1, spot + 4, 24)] });
  players.push({ id: "er", team: "def", role: "d", start: { x: los + 1.5, y: 48 }, keyframes: [kf(0, los + 1.5, 48), kf(0.55, spot + 4, 36), kf(1, spot + 4, 36)] });
  players.push(still("lb1", "def", "d", los + 6, 20), still("lb2", "def", "d", los + 6, 40));
  players.push(still("ret1", "def", "d", goal + 3, 24), still("ret2", "def", "d", goal + 3, 36));

  const apexX = (spot + goal) / 2;
  const ballKeyframes: BallKeyframe[] = [
    { t: 0, x: los, y: 30, z: 0 }, { t: 0.12, x: los, y: 30, z: 0.05 },
    { t: 0.26, x: spot, y: 30, z: 0 }, { t: 0.5, x: spot, y: 30, z: 0 },
  ];
  const events: PlayEvent[] = [{ t: 0.12, type: "snap", label: "Snap" }, { t: 0.26, type: "place", label: "Set" }, { t: 0.5, type: "kick", label: "Kick" }];
  if (result === "blocked") { ballKeyframes.push({ t: 0.6, x: los + 3, y: 30, z: 0.5 }, { t: 0.72, x: los + 1, y: 26, z: 0.1 }, { t: 1, x: los - 2, y: 24, z: 0 }); events.push({ t: 0.6, type: "block", label: "Blocked!" }); }
  else if (result === "miss") { ballKeyframes.push({ t: 0.65, x: apexX, y: 30, z: 1 }, { t: 0.84, x: goal, y: 38, z: 0.5 }, { t: 1, x: goal + 4, y: 42, z: 0 }); events.push({ t: 0.84, type: "miss", label: "No good" }); }
  else { ballKeyframes.push({ t: 0.65, x: apexX, y: 30, z: 1 }, { t: 0.82, x: goal, y: 30, z: 0.45 }, { t: 1, x: goal + 5, y: 30, z: 0 }); events.push({ t: 0.82, type: "through", label: "Good!" }, { t: 0.9, type: "score", label: "+3" }); }
  return { surface: "field", kind: "field_goal", result, durationMs: 6500, los, goal, players, ballKeyframes, events, annotations: [] };
}

function passTd(input: PlayInput): PlaySchema {
  const goal = 92, los = 40, qb = los - 8;
  const n = names(input.description);
  const players: PlayerSpec[] = [];
  // O-line
  [-6, -3, 0, 3, 6].forEach((dy, i) => players.push(still(`ol${i}`, "off", "ol", los, 30 + dy, -0.4)));
  // QB drops, throws
  players.push({ id: "qb", team: "off", role: "ball", label: n.leadLast || "QB", start: { x: qb, y: 30 }, keyframes: [kf(0, qb, 30), kf(0.25, qb - 3, 30), kf(0.45, qb - 3, 30), kf(1, qb - 3, 30)] });
  // Receiver runs a route to the end zone
  players.push({ id: "wr", team: "off", role: "target", label: n.assistLast || "WR", start: { x: los, y: 50 }, keyframes: [kf(0, los, 50), kf(0.45, los + 22, 44), kf(0.78, goal - 2, 32), kf(1, goal + 2, 30)] });
  players.push(still("wr2", "off", "wr", los, 10, 12));
  // Defenders
  [{ x: los + 3, y: 24 }, { x: los + 3, y: 36 }, { x: los + 8, y: 30 }].forEach((p, i) => players.push({ id: `d${i}`, team: "def", role: "d", start: p, keyframes: [kf(0, p.x, p.y), kf(0.55, p.x + 6, p.y), kf(1, p.x + 12, p.y)] }));
  players.push({ id: "cb", team: "def", role: "d", start: { x: los + 6, y: 48 }, keyframes: [kf(0, los + 6, 48), kf(0.6, los + 24, 42), kf(1, goal - 4, 33)] });
  [16, 44].forEach((y, i) => players.push(still(`s${i}`, "def", "d", goal - 14, y)));
  [20, 40].forEach((y, i) => players.push(still(`lb${i}`, "def", "d", los + 5, y)));

  const ballKeyframes: BallKeyframe[] = [{ t: 0, x: qb, y: 30, z: 0 }, { t: 0.25, x: qb - 3, y: 30, z: 0 }, { t: 0.45, x: qb - 3, y: 30, z: 0.1 }, { t: 0.62, x: los + 18, y: 40, z: 1 }, { t: 0.8, x: goal - 4, y: 33, z: 0.3 }, { t: 0.88, x: goal, y: 30, z: 0 }, { t: 1, x: goal, y: 30, z: 0 }];
  const events: PlayEvent[] = [{ t: 0.08, type: "snap", label: "Snap" }, { t: 0.45, type: "throw", label: "Throw" }, { t: 0.8, type: "catch", label: "Caught!" }, { t: 0.9, type: "score", label: "TD" }];
  return { surface: "field", kind: "pass_td", result: "score", durationMs: 6500, los, goal, players, ballKeyframes, events, annotations: [] };
}

function runPlay(input: PlayInput, isTd: boolean): PlaySchema {
  const goal = 92, los = 38;
  const n = names(input.description);
  const endX = isTd ? goal : los + 26;
  const players: PlayerSpec[] = [];
  [-6, -3, 0, 3, 6].forEach((dy, i) => players.push({ id: `ol${i}`, team: "off", role: "ol", start: { x: los, y: 30 + dy }, keyframes: [kf(0, los, 30 + dy), kf(1, los + 10, 30 + dy * 0.6)] }));
  players.push({ id: "rb", team: "off", role: "ball", label: n.leadLast || "RB", start: { x: los - 5, y: 30 }, keyframes: [kf(0, los - 5, 30), kf(0.3, los + 2, 26), kf(0.6, (los + endX) / 2, 33), kf(1, endX, 30)] });
  for (let i = 0; i < 7; i++) { const y = 14 + i * 5; players.push({ id: `d${i}`, team: "def", role: "d", start: { x: los + 4 + (i % 3) * 4, y }, keyframes: [kf(0, los + 4 + (i % 3) * 4, y), kf(1, endX - 6, 30 + (y - 30) * 0.4)] }); }
  const ballKeyframes: BallKeyframe[] = [{ t: 0, x: los - 5, y: 30, z: 0 }, { t: 0.3, x: los + 2, y: 26, z: 0 }, { t: 0.6, x: (los + endX) / 2, y: 33, z: 0 }, { t: 1, x: endX, y: 30, z: 0 }];
  const events: PlayEvent[] = [{ t: 0.08, type: "snap", label: "Handoff" }];
  if (isTd) events.push({ t: 0.92, type: "score", label: "TD" });
  return { surface: "field", kind: isTd ? "run_td" : "run", result: isTd ? "score" : "play", durationMs: 6000, los, goal, players, ballKeyframes, events, annotations: [] };
}

function turnover(input: PlayInput): PlaySchema {
  const goal = 92, los = 55;
  const n = names(input.description);
  const players: PlayerSpec[] = [];
  players.push({ id: "qb", team: "off", role: "off", start: { x: los - 8, y: 30 }, keyframes: [kf(0, los - 8, 30), kf(0.4, los - 9, 30), kf(1, los - 9, 30)] });
  // Defender jumps the route and returns the other way
  players.push({ id: "int", team: "def", role: "ball", label: n.leadLast || "INT", start: { x: los + 8, y: 40 }, keyframes: [kf(0, los + 8, 40), kf(0.4, los + 2, 34), kf(0.55, los, 32), kf(1, 16, 28)] });
  [{ x: los, y: 18 }, { x: los, y: 30 }, { x: los, y: 42 }].forEach((p, i) => players.push(still(`o${i}`, "off", "ol", p.x, p.y, -10)));
  for (let i = 0; i < 5; i++) players.push(still(`d${i}`, "def", "d", los + 6 + i, 16 + i * 7, -16));
  const ballKeyframes: BallKeyframe[] = [{ t: 0, x: los - 8, y: 30, z: 0 }, { t: 0.3, x: los + 4, y: 36, z: 0.6 }, { t: 0.4, x: los + 2, y: 34, z: 0 }, { t: 1, x: 16, y: 28, z: 0 }];
  return { surface: "field", kind: "turnover", result: "play", durationMs: 6000, los, goal, players, ballKeyframes,
    events: [{ t: 0.08, type: "snap", label: "Snap" }, { t: 0.32, type: "block", label: "Intercepted!" }], annotations: [] };
}

function sackPlay(input: PlayInput): PlaySchema {
  const goal = 92, los = 45, qb = los - 8;
  const n = names(input.description);
  const players: PlayerSpec[] = [];
  [-5, -2.5, 0, 2.5, 5].forEach((dy, i) => players.push(still(`ol${i}`, "off", "ol", los, 30 + dy)));
  players.push({ id: "qb", team: "off", role: "ball", label: "QB", start: { x: qb, y: 30 }, keyframes: [kf(0, qb, 30), kf(0.3, qb - 3, 30), kf(0.6, qb - 2, 29), kf(0.7, qb - 1, 30), kf(1, qb - 1, 30)] });
  players.push({ id: "edge", team: "def", role: "ball", label: n.leadLast || "Sack", start: { x: los + 2, y: 46 }, keyframes: [kf(0, los + 2, 46), kf(0.45, qb + 4, 36), kf(0.68, qb - 1, 30.5), kf(1, qb - 1, 30.5)] });
  [{ x: los + 2, y: 22 }, { x: los + 2, y: 30 }, { x: los + 2, y: 38 }].forEach((p, i) => players.push({ id: `r${i}`, team: "def", role: "d", start: p, keyframes: [kf(0, p.x, p.y), kf(0.6, qb + 5, p.y * 0.5 + 15), kf(1, qb + 4, 30)] }));
  const ballKeyframes: BallKeyframe[] = [{ t: 0, x: qb, y: 30, z: 0 }, { t: 0.6, x: qb - 2, y: 29, z: 0 }, { t: 1, x: qb - 1, y: 30, z: 0 }];
  return { surface: "field", kind: "sack", result: "play", durationMs: 5500, los, goal, players, ballKeyframes,
    events: [{ t: 0.08, type: "snap", label: "Snap" }, { t: 0.68, type: "block", label: "Sack!" }], annotations: [] };
}

/* ════════════════════ NBA ════════════════════ */
function nbaShot(input: PlayInput, kind: "three" | "dunk" | "layup" | "jumper"): PlaySchema {
  const hoop = 90;
  const n = names(input.description);
  const made = !input.description.toLowerCase().includes("miss");
  const handler = { x: 24, y: 30 };
  const shooter = kind === "three" ? { x: 58, y: 12 } : { x: 62, y: 36 };
  const players: PlayerSpec[] = [];
  // Ball handler passes, then spots up
  players.push({ id: "pg", team: "off", role: n.assist ? "off" : "ball", label: n.assist ? (n.assistLast || "PG") : undefined, start: handler, keyframes: [kf(0, handler.x, handler.y), kf(0.3, handler.x + 6, handler.y), kf(1, handler.x + 4, handler.y - 6)] });
  // Shooter receives and scores
  const drive = kind === "dunk" || kind === "layup";
  players.push({ id: "sh", team: "off", role: "ball", label: n.leadLast || "Shooter",
    start: { x: shooter.x - (drive ? 10 : 0), y: shooter.y },
    keyframes: drive
      ? [kf(0, shooter.x - 10, shooter.y), kf(0.35, shooter.x, shooter.y), kf(0.62, shooter.x + 8, 32), kf(0.8, hoop - 4, 30), kf(1, hoop - 4, 30)]
      : [kf(0, shooter.x, shooter.y), kf(0.35, shooter.x, shooter.y), kf(0.55, shooter.x, shooter.y), kf(1, shooter.x, shooter.y)] });
  players.push(still("o3", "off", "off", 40, 48), still("o4", "off", "off", 70, 18), still("o5", "off", "off", 50, 30));
  // Defenders
  [{ x: handler.x + 5, y: 30 }, { x: shooter.x + (drive ? 0 : 4), y: shooter.y + 3 }, { x: 46, y: 46 }, { x: 72, y: 22 }, { x: hoop - 8, y: 30 }].forEach((p, i) =>
    players.push({ id: `d${i}`, team: "def", role: "d", start: p, keyframes: [kf(0, p.x, p.y), kf(0.6, p.x + (drive && i === 4 ? -2 : 3), p.y), kf(1, p.x + 4, p.y)] }));

  // Ball: handler -> pass -> shooter -> shot arc to hoop
  const passT = 0.3, shotT = drive ? 0.66 : 0.55, scoreT = drive ? 0.82 : 0.78;
  const ballKeyframes: BallKeyframe[] = [
    { t: 0, x: handler.x, y: handler.y, z: 0.15 },
    { t: passT, x: handler.x + 6, y: handler.y, z: 0.2 },
    { t: shotT, x: shooter.x, y: shooter.y, z: 0.2 },
  ];
  if (made && kind === "three") ballKeyframes.push({ t: (shotT + scoreT) / 2, x: (shooter.x + hoop) / 2, y: (shooter.y + 30) / 2, z: 1 }, { t: scoreT, x: hoop, y: 30, z: 0.4 }, { t: 1, x: hoop, y: 31, z: 0 });
  else if (made) ballKeyframes.push({ t: shotT + 0.06, x: shooter.x + 6, y: 31, z: drive ? 0.6 : 0.7 }, { t: scoreT, x: hoop, y: 30, z: 0.4 }, { t: 1, x: hoop, y: 31, z: 0 });
  else ballKeyframes.push({ t: (shotT + scoreT) / 2, x: (shooter.x + hoop) / 2, y: 28, z: 1 }, { t: scoreT, x: hoop - 1, y: 27, z: 0.5 }, { t: 1, x: hoop - 6, y: 24, z: 0 });

  const events: PlayEvent[] = [{ t: passT, type: "pass", label: n.assist ? "Dish" : "Bring it" }, { t: shotT, type: kind === "dunk" ? "kick" : "throw", label: kind === "dunk" ? "Rises up" : "Shot" }];
  if (made) events.push({ t: scoreT, type: "through", label: kind === "dunk" ? "SLAM!" : "Splash!" }, { t: scoreT + 0.06, type: "score", label: kind === "three" ? "+3" : "+2" });
  else events.push({ t: scoreT, type: "miss", label: "Miss" });
  return { surface: "court", kind: `nba_${kind}`, result: made ? "score" : "miss", durationMs: 5500, los: shooter.x, goal: hoop, players, ballKeyframes, events, annotations: [] };
}

/* ════════════════════ dispatcher ════════════════════ */
export function buildPlaySchema(input: PlayInput): PlaySchema {
  if ((input.sport || "").toUpperCase() === "NBA") {
    const d = input.description.toLowerCase();
    if (input.playType === "three_pointer") return nbaShot(input, "three");
    if (input.playType === "dunk") return nbaShot(input, "dunk");
    if (d.includes("layup")) return nbaShot(input, "layup");
    return nbaShot(input, "jumper");
  }
  switch (input.playType) {
    case "field_goal": return fieldGoal(input);
    case "touchdown": return /pass|to .* for/i.test(input.description) && !/up the middle|left|right (end|tackle|guard)/i.test(input.description) ? passTd(input) : runPlay(input, true);
    case "interception": return turnover(input);
    case "sack": return sackPlay(input);
    default: return runPlay(input, false);
  }
}

export function sampleTrack<T extends { t: number }>(frames: T[], t: number, lerp: (a: T, b: T, f: number) => T): T {
  if (frames.length === 0) throw new Error("empty track");
  if (t <= frames[0].t) return frames[0];
  if (t >= frames[frames.length - 1].t) return frames[frames.length - 1];
  for (let i = 0; i < frames.length - 1; i++) {
    const a = frames[i], b = frames[i + 1];
    if (t >= a.t && t <= b.t) { const f = b.t === a.t ? 0 : (t - a.t) / (b.t - a.t); return lerp(a, b, f); }
  }
  return frames[frames.length - 1];
}
