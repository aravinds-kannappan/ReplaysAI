/* ──────────────────────────────────────────────────────────────────────────
   Play animation schema + generators.

   A play is described declaratively as players (each with a start point and
   timed keyframes), a ball trajectory, and discrete events. A renderer
   (FootballPlayAnimation) interpolates this over a normalized timeline t∈[0,1].
   Field coordinates use a 100 × 60 top-down field (x→ toward the goal, which is
   on the right; uprights at x≈94).
   ────────────────────────────────────────────────────────────────────────── */

export type Vec = { x: number; y: number };
export type PlayerKeyframe = { t: number; x: number; y: number };
export type Team = "kick" | "defense";

export type PlayerSpec = {
  id: string;
  team: Team;
  role: string;        // K, H, LS, OL, W, R, E, RET …
  label: string;       // shown under the marker
  start: Vec;
  keyframes: PlayerKeyframe[];
};

export type BallKeyframe = { t: number; x: number; y: number; z?: number }; // z = height 0..1
export type PlayEvent = { t: number; type: "snap" | "place" | "approach" | "kick" | "through" | "miss" | "block" | "score"; label?: string };

export type PlaySchema = {
  kind: "field_goal" | "touchdown" | "turnover" | "generic";
  result: "good" | "miss" | "blocked" | "score" | "play";
  durationMs: number;
  los: number;                 // x of the line of scrimmage
  uprights: number;            // x of the uprights
  players: PlayerSpec[];
  ballKeyframes: BallKeyframe[];
  events: PlayEvent[];
};

export type PlayInput = {
  playType: string;
  description: string;
  fgDistance?: number | null;
  yardsToGoal?: number | null;
  kickingAbbr: string;
  defenseAbbr: string;
};

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function namesFromDescription(desc: string) {
  const kicker = /^([A-Z]\.[A-Za-z'-]+)/.exec(desc)?.[1];
  const holder = /Holder-([A-Z]\.[A-Za-z'-]+)/.exec(desc)?.[1];
  const center = /Center-([A-Z]\.[A-Za-z'-]+)/.exec(desc)?.[1];
  return { kicker, holder, center };
}

/* ── Field goal: the full sequence ─────────────────────────────────────────── */
export function buildFieldGoalSchema(input: PlayInput): PlaySchema {
  const uprights = 94;
  const goalLine = 88;
  const yardsToGoal = clamp(input.yardsToGoal ?? (input.fgDistance ? input.fgDistance - 17 : 25), 3, 55);
  const los = clamp(goalLine - yardsToGoal * 1.25, 24, 76);
  const spot = los - 7.5;           // hold spot, ~7.5 yds behind LOS
  const names = namesFromDescription(input.description);
  const desc = input.description.toLowerCase();
  const result: PlaySchema["result"] = desc.includes("blocked") ? "blocked" : desc.includes("no good") || desc.includes("missed") ? "miss" : "good";

  const players: PlayerSpec[] = [];
  const still = (id: string, team: Team, role: string, label: string, x: number, y: number, push = 0): PlayerSpec => ({
    id, team, role, label, start: { x, y }, keyframes: [{ t: 0, x, y }, { t: 0.55, x: x + push, y }, { t: 1, x: x + push, y }],
  });

  // ── Kicking unit (11): long snapper, 6 linemen, 2 wings, holder, kicker ──
  players.push(still("ls", "kick", "LS", names.center || "LS", los, 30, -0.6));
  [-9, -6, -3, 3, 6, 9].forEach((dy, i) => players.push(still(`ol${i}`, "kick", "OL", "OL", los, 30 + dy, -0.5)));
  players.push(still("wl", "kick", "W", "W", los, 13, -0.4));
  players.push(still("wr", "kick", "W", "W", los, 47, -0.4));

  // Holder kneels at the spot, ball arrives at place time.
  players.push({
    id: "h", team: "kick", role: "H", label: names.holder || "Holder",
    start: { x: spot - 1.5, y: 30 },
    keyframes: [{ t: 0, x: spot - 1.5, y: 30 }, { t: 0.26, x: spot, y: 30 }, { t: 1, x: spot, y: 30 }],
  });
  // Kicker approaches the ball in three steps, then plants.
  const kStart = { x: spot - 4, y: 33.5 };
  players.push({
    id: "k", team: "kick", role: "K", label: names.kicker || "K",
    start: kStart,
    keyframes: [
      { t: 0, ...kStart }, { t: 0.30, x: spot - 3, y: 32.5 },
      { t: 0.38, x: spot - 2.1, y: 31.6 }, { t: 0.46, x: spot - 1.2, y: 30.6 },
      { t: 0.5, x: spot - 0.6, y: 30 }, { t: 1, x: spot - 0.6, y: 30 },
    ],
  });

  // ── Defense (11): interior rush, edges, second level, two deep returners ──
  const rush = (id: string, y: number) => ({
    id, team: "defense" as Team, role: "R", label: "R",
    start: { x: los + 2.2, y },
    keyframes: [{ t: 0, x: los + 2.2, y }, { t: 0.12, x: los + 2.2, y }, { t: 0.55, x: spot + 2.5, y: 30 + (y - 30) * 0.3 }, { t: 1, x: spot + 2.5, y: 30 + (y - 30) * 0.3 }],
  });
  [22, 26, 30, 34, 38].forEach((y, i) => players.push(rush(`r${i}`, y)));
  players.push({ id: "el", team: "defense", role: "E", label: "E", start: { x: los + 1.5, y: 12 }, keyframes: [{ t: 0, x: los + 1.5, y: 12 }, { t: 0.55, x: spot + 4, y: 24 }, { t: 1, x: spot + 4, y: 24 }] });
  players.push({ id: "er", team: "defense", role: "E", label: "E", start: { x: los + 1.5, y: 48 }, keyframes: [{ t: 0, x: los + 1.5, y: 48 }, { t: 0.55, x: spot + 4, y: 36 }, { t: 1, x: spot + 4, y: 36 }] });
  players.push(still("lb1", "defense", "LB", "LB", los + 6, 20));
  players.push(still("lb2", "defense", "LB", "LB", los + 6, 40));
  players.push(still("ret1", "defense", "RET", "RET", uprights + 3, 24));
  players.push(still("ret2", "defense", "RET", "RET", uprights + 3, 36));

  // ── Ball trajectory: snap → place → kick → arc → through (or block/miss) ──
  const apexX = (spot + uprights) / 2;
  const ballKeyframes: BallKeyframe[] = [
    { t: 0, x: los, y: 30, z: 0 },
    { t: 0.12, x: los, y: 30, z: 0.05 },
    { t: 0.26, x: spot, y: 30, z: 0 },           // snapped back into the hold
    { t: 0.5, x: spot, y: 30, z: 0 },            // placed, waiting for the kick
  ];
  const events: PlayEvent[] = [
    { t: 0.12, type: "snap", label: "Snap" },
    { t: 0.26, type: "place", label: "Set" },
    { t: 0.3, type: "approach", label: "Approach" },
    { t: 0.5, type: "kick", label: "Kick" },
  ];
  if (result === "blocked") {
    ballKeyframes.push({ t: 0.6, x: los + 3, y: 30, z: 0.5 }, { t: 0.72, x: los + 1, y: 26, z: 0.1 }, { t: 1, x: los - 2, y: 24, z: 0 });
    events.push({ t: 0.6, type: "block", label: "Blocked!" });
  } else if (result === "miss") {
    ballKeyframes.push({ t: 0.65, x: apexX, y: 30, z: 1 }, { t: 0.84, x: uprights, y: 38, z: 0.5 }, { t: 1, x: uprights + 4, y: 42, z: 0 });
    events.push({ t: 0.84, type: "miss", label: "No good" }, { t: 0.9, type: "score", label: "No points" });
  } else {
    ballKeyframes.push({ t: 0.65, x: apexX, y: 30, z: 1 }, { t: 0.82, x: uprights, y: 30, z: 0.45 }, { t: 0.92, x: uprights + 3, y: 30, z: 0.2 }, { t: 1, x: uprights + 5, y: 30, z: 0 });
    events.push({ t: 0.82, type: "through", label: "Good!" }, { t: 0.9, type: "score", label: "+3" });
  }

  return { kind: "field_goal", result, durationMs: 9000, los, uprights, players, ballKeyframes, events };
}

/* ── Generic / non-FG plays: a simpler downfield animation ──────────────────── */
export function buildGenericSchema(input: PlayInput): PlaySchema {
  const uprights = 94;
  const reverse = ["interception", "turnover", "fumble"].includes(input.playType);
  const isTD = input.playType === "touchdown";
  const startX = reverse ? 70 : 30;
  const endX = reverse ? 14 : isTD ? 90 : 64;

  const players: PlayerSpec[] = [];
  // Ball carrier
  players.push({
    id: "carrier", team: reverse ? "defense" : "kick", role: "BALL", label: reverse ? "INT" : "RB",
    start: { x: startX, y: 30 },
    keyframes: [{ t: 0, x: startX, y: 30 }, { t: 0.5, x: (startX + endX) / 2, y: 26 }, { t: 1, x: endX, y: 30 }],
  });
  // Blockers + defenders flowing
  for (let i = 0; i < 6; i++) {
    const y = 16 + i * 5;
    players.push({ id: `o${i}`, team: "kick", role: "OL", label: "OL", start: { x: startX - 4, y }, keyframes: [{ t: 0, x: startX - 4, y }, { t: 1, x: endX - 8, y: y + (reverse ? -2 : 2) }] });
    players.push({ id: `d${i}`, team: "defense", role: "D", label: "D", start: { x: startX + 8, y: y + 2 }, keyframes: [{ t: 0, x: startX + 8, y: y + 2 }, { t: 1, x: endX - 2, y } ] });
  }
  // 10 + carrier = 13 players for the generic flow (kept lighter than the FG set).

  const events: PlayEvent[] = [{ t: 0.08, type: "snap", label: "Snap" }];
  const ballKeyframes: BallKeyframe[] = [{ t: 0, x: startX, y: 30, z: 0 }, { t: 0.5, x: (startX + endX) / 2, y: 26, z: 0.1 }, { t: 1, x: endX, y: 30, z: 0 }];
  if (isTD) { events.push({ t: 0.92, type: "through", label: "Touchdown!" }, { t: 0.96, type: "score", label: "+6" }); }
  else if (reverse) { events.push({ t: 0.2, type: "block", label: "Takeaway!" }); }

  return { kind: isTD ? "touchdown" : reverse ? "turnover" : "generic", result: isTD ? "score" : "play", durationMs: 6500, los: startX, uprights, players, ballKeyframes, events };
}

export function buildPlaySchema(input: PlayInput): PlaySchema {
  return input.playType === "field_goal" ? buildFieldGoalSchema(input) : buildGenericSchema(input);
}

/* Interpolate a keyframe track at time t (linear between surrounding frames). */
export function sampleTrack<T extends { t: number }>(frames: T[], t: number, lerp: (a: T, b: T, f: number) => T): T {
  if (frames.length === 0) throw new Error("empty track");
  if (t <= frames[0].t) return frames[0];
  if (t >= frames[frames.length - 1].t) return frames[frames.length - 1];
  for (let i = 0; i < frames.length - 1; i++) {
    const a = frames[i], b = frames[i + 1];
    if (t >= a.t && t <= b.t) {
      const f = b.t === a.t ? 0 : (t - a.t) / (b.t - a.t);
      return lerp(a, b, f);
    }
  }
  return frames[frames.length - 1];
}
