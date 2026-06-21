import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { apiPath } from "../lib/api";
import "./Landing.css";

/* ── Waitlist (unchanged contract) ── */
function Waitlist() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("loading");
    try {
      const res = await axios.post(apiPath("/api/waitlist"), { email: email.trim(), source: "landing" });
      if (res.data?.status === "ok") {
        setStatus("ok");
        setMessage(res.data.message || "You're on the list.");
        setEmail("");
      } else {
        setStatus("error");
        setMessage(res.data?.message || "Please enter a valid email.");
      }
    } catch {
      setStatus("error");
      setMessage("Could not reach the waitlist service. Try again.");
    }
  }
  return (
    <form className="waitlist" onSubmit={submit}>
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@email.com" aria-label="Email for waitlist" />
      <button type="submit" disabled={status === "loading"}>{status === "loading" ? "Joining..." : "Join waitlist"}</button>
      {status === "ok" && <p className="waitlist-msg ok">{message}</p>}
      {status === "error" && <p className="waitlist-msg error">{message}</p>}
    </form>
  );
}

/* ── The four named specialist agents ── */
const AGENTS = [
  { id: "scout", name: "ScoutAgent", role: "player tracking", blurb: "Reads the floor in real time — spacing, the transition trigger, who's open." },
  { id: "stat", name: "StatAgent", role: "live numbers", blurb: "Surfaces the stat line and run that actually decide the possession." },
  { id: "ref", name: "RefAgent", role: "rulebook", blurb: "Explains the call — verticality, continuation, the clause behind the whistle." },
  { id: "predict", name: "PredictAgent", role: "win probability", blurb: "Moves the win-probability arc as the play swings the game." },
] as const;

/* A scripted half-court possession the hero loops through. Orb motion is
   illustrative — the free data feed has no x/y tracking, so this is a stylized
   broadcast animation, not measured positions. */
type Pt = { x: number; y: number };
type Step = { pbp: string; agent: number; players: Pt[]; ball: Pt; hud: string };

const PLAY: Step[] = [
  {
    pbp: "Defensive board — guard pushes it in transition.",
    agent: 0,
    players: [{ x: 22, y: 50 }, { x: 30, y: 24 }, { x: 30, y: 76 }, { x: 40, y: 40 }, { x: 40, y: 62 }],
    ball: { x: 22, y: 50 },
    hud: "Tracking 5 · transition trigger · pace +12",
  },
  {
    pbp: "Swing to the wing, the defense rotates over.",
    agent: 1,
    players: [{ x: 35, y: 50 }, { x: 46, y: 20 }, { x: 48, y: 78 }, { x: 52, y: 46 }, { x: 54, y: 62 }],
    ball: { x: 46, y: 20 },
    hud: "Team on a 9–2 run · 3PT 41% · +6 paint",
  },
  {
    pbp: "Drive collapses the help defender into the paint.",
    agent: 2,
    players: [{ x: 50, y: 50 }, { x: 62, y: 28 }, { x: 58, y: 76 }, { x: 67, y: 48 }, { x: 60, y: 62 }],
    ball: { x: 67, y: 48 },
    hud: "Verticality — legal contest, no foul (NBA 12-B)",
  },
  {
    pbp: "Kick-out to the corner — catch and rise.",
    agent: 3,
    players: [{ x: 60, y: 54 }, { x: 70, y: 18 }, { x: 86, y: 82 }, { x: 72, y: 50 }, { x: 74, y: 62 }],
    ball: { x: 86, y: 82 },
    hud: "Win probability 62% → 71%",
  },
  {
    pbp: "Corner three splashes — the lead extends.",
    agent: 3,
    players: [{ x: 62, y: 54 }, { x: 72, y: 18 }, { x: 88, y: 80 }, { x: 74, y: 50 }, { x: 76, y: 62 }],
    ball: { x: 95, y: 50 },
    hud: "Win probability 71% → 78% · shot made",
  },
];

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = () => setReduced(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return reduced;
}

/* Broadcast phases drive which HUD is active + the live ticker/win-prob. The
   canvas animation underneath runs continuously, independent of these. */
const PHASES = [
  { agent: 0, pbp: "Defensive board — guard ignites the break.", wp: 58, hud: "Tracking 10 · transition" },
  { agent: 1, pbp: "Swing to the wing, defense scrambles to rotate.", wp: 63, hud: "On a 9–2 run · 3PT 41%" },
  { agent: 2, pbp: "Drive draws the help — legal verticality, no foul.", wp: 66, hud: "Verticality · clean (12-B)" },
  { agent: 3, pbp: "Kick-out to the corner, catch and rise…", wp: 71, hud: "Win prob climbing" },
  { agent: 3, pbp: "Corner three splashes — the lead extends.", wp: 78, hud: "Shot made · +6" },
];

function CourtHud({ index, active, value }: { index: number; active: boolean; value: string }) {
  const agent = AGENTS[index];
  return (
    <div className={`court-hud hud-${agent.id} ${active ? "active" : ""}`}>
      <span className="hud-tag">{agent.name} · {agent.role}</span>
      <strong className="hud-value">{value}</strong>
    </div>
  );
}

/* Continuous canvas court: drifting players, a passing ball with a glowing
   trail, and a sweeping broadcast scan line. */
function useCourtCanvas(canvasRef: React.RefObject<HTMLCanvasElement | null>, reduced: boolean) {
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    let W = 0, H = 0;
    const resize = () => {
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    // 5 offensive players, 5 defenders — each drifts within a zone.
    const off = [
      { bx: 0.26, by: 0.5, ax: 0.05, ay: 0.16, sx: 0.7, sy: 0.9, px: 0, py: 1 },
      { bx: 0.46, by: 0.24, ax: 0.06, ay: 0.08, sx: 0.8, sy: 1.1, px: 2, py: 0 },
      { bx: 0.5, by: 0.78, ax: 0.07, ay: 0.07, sx: 0.6, sy: 0.8, px: 1, py: 3 },
      { bx: 0.68, by: 0.46, ax: 0.08, ay: 0.12, sx: 0.9, sy: 0.7, px: 4, py: 2 },
      { bx: 0.78, by: 0.66, ax: 0.06, ay: 0.1, sx: 0.75, sy: 1.0, px: 3, py: 5 },
    ];
    const posAt = (p: typeof off[number], t: number) => ({
      x: (p.bx + p.ax * Math.sin(t * p.sx + p.px)) * W,
      y: (p.by + p.ay * Math.cos(t * p.sy + p.py)) * H,
    });

    const trail: { x: number; y: number }[] = [];
    let holder = 0, prevHolder = 0, passT = 0;
    let t = 0, raf = 0, last = performance.now();

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now; t += dt;
      ctx.clearRect(0, 0, W, H);

      // court markings
      ctx.strokeStyle = "rgba(255,255,255,0.10)";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(W * 0.04, H * 0.1, W * 0.92, H * 0.8);
      ctx.beginPath(); ctx.moveTo(W / 2, H * 0.1); ctx.lineTo(W / 2, H * 0.9); ctx.stroke();
      ctx.beginPath(); ctx.arc(W / 2, H / 2, Math.min(W, H) * 0.13, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = "rgba(255,179,71,0.55)";
      ctx.beginPath(); ctx.arc(W * 0.95, H / 2, 5, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(W * 0.05, H / 2, 5, 0, Math.PI * 2); ctx.stroke();

      // defenders (dim)
      for (const p of off) {
        const q = posAt(p, t + 0.6);
        ctx.fillStyle = "rgba(120,140,150,0.35)";
        ctx.beginPath(); ctx.arc(q.x + 16, q.y - 12, 6, 0, Math.PI * 2); ctx.fill();
      }

      // ball pass logic
      passT += dt;
      if (passT > 1.7) { passT = 0; prevHolder = holder; holder = (holder + 1 + Math.floor(Math.random() * 2)) % off.length; }
      const e = Math.min(1, passT / 1.0);
      const ease = e < 0.5 ? 2 * e * e : 1 - Math.pow(-2 * e + 2, 2) / 2;
      const a = posAt(off[prevHolder], t), b = posAt(off[holder], t);
      const ball = { x: a.x + (b.x - a.x) * ease, y: a.y + (b.y - a.y) * ease };

      // offensive orbs (glow)
      for (let i = 0; i < off.length; i++) {
        const p = posAt(off[i], t);
        const isHolder = i === holder;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, isHolder ? 22 : 16);
        g.addColorStop(0, "rgba(234,255,247,0.95)");
        g.addColorStop(0.4, "rgba(24,216,143,0.9)");
        g.addColorStop(1, "rgba(24,216,143,0)");
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(p.x, p.y, isHolder ? 22 : 16, 0, Math.PI * 2); ctx.fill();
      }

      // ball trail
      trail.push(ball); if (trail.length > 18) trail.shift();
      for (let i = 0; i < trail.length; i++) {
        const alpha = (i / trail.length) * 0.5;
        ctx.fillStyle = `rgba(255,179,71,${alpha})`;
        ctx.beginPath(); ctx.arc(trail[i].x, trail[i].y, 2 + (i / trail.length) * 4, 0, Math.PI * 2); ctx.fill();
      }
      const bg = ctx.createRadialGradient(ball.x, ball.y, 0, ball.x, ball.y, 12);
      bg.addColorStop(0, "rgba(255,242,207,1)");
      bg.addColorStop(1, "rgba(255,179,71,0)");
      ctx.fillStyle = bg;
      ctx.beginPath(); ctx.arc(ball.x, ball.y, 12, 0, Math.PI * 2); ctx.fill();

      // broadcast scan line
      const scanX = ((t * 0.12) % 1) * W;
      const sg = ctx.createLinearGradient(scanX - 40, 0, scanX + 40, 0);
      sg.addColorStop(0, "rgba(66,214,255,0)");
      sg.addColorStop(0.5, "rgba(66,214,255,0.10)");
      sg.addColorStop(1, "rgba(66,214,255,0)");
      ctx.fillStyle = sg;
      ctx.fillRect(scanX - 40, H * 0.1, 80, H * 0.8);

      if (!reduced) raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [canvasRef, reduced]);
}

function CourtHero() {
  const reduced = usePrefersReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [phase, setPhase] = useState(0);
  const [wp, setWp] = useState(54);
  useCourtCanvas(canvasRef, reduced);

  useEffect(() => {
    if (reduced) return;
    const id = window.setInterval(() => setPhase((p) => (p + 1) % PHASES.length), 3000);
    return () => window.clearInterval(id);
  }, [reduced]);
  useEffect(() => {
    const target = PHASES[phase].wp;
    if (reduced) {
      const id = window.setTimeout(() => setWp(target), 0);
      return () => window.clearTimeout(id);
    }
    const id = window.setInterval(() => {
      setWp((v) => (Math.abs(target - v) < 1 ? target : v + Math.sign(target - v)));
    }, 45);
    return () => window.clearInterval(id);
  }, [phase, reduced]);

  const frame = PHASES[phase];

  return (
    <section className="lp-hero">
      <div className="lp-noise" aria-hidden />
      <div className="lp-hero-inner">
        <div className="lp-hero-copy">
          <div className="brand-lockup"><img src="/replaysai-logo.svg" alt="ReplaysAI logo" /><span>Replays<b>AI</b></span></div>
          <span className="lp-kicker">Four specialist agents · one broadcast brain</span>
          <h1>The Game Has a<br /><em>New Brain.</em></h1>
          <p>
            ScoutAgent, StatAgent, RefAgent, and PredictAgent watch every possession together —
            tracking players, surfacing the numbers, explaining the calls, and moving the win
            probability live. Then they turn it into a feed and narrated reels built for <strong>you</strong>.
          </p>
          <div className="lp-actions">
            <Link to="/onboarding" className="cta-primary">Assemble Your Squad</Link>
            <a href="#agents" className="cta-ghost">Meet the agents</a>
          </div>
        </div>

        <div className="lp-court-wrap" aria-hidden>
          <div className="lp-court">
            <canvas ref={canvasRef} className="court-canvas" />
            {AGENTS.map((_, i) => (
              <CourtHud
                key={i}
                index={i}
                active={i === frame.agent}
                value={i === frame.agent ? (i === 3 ? `${wp}% win prob` : frame.hud) : AGENTS[i].role}
              />
            ))}
          </div>

          <div className="court-ticker">
            <span className="ticker-live">● LIVE</span>
            <span className="ticker-text" key={phase}>{frame.pbp}</span>
            <span className="ticker-clock">Q4 · 4:12</span>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Meet the agents ── */
function MeetTheAgents() {
  return (
    <section id="agents" className="lp-section">
      <span className="lp-kicker">Meet the agents</span>
      <h2>Four minds on every play.</h2>
      <div className="agent-grid">
        {AGENTS.map((a) => (
          <div key={a.id} className={`agent-card card-${a.id}`}>
            <span className="agent-card-role">{a.role}</span>
            <strong>{a.name}</strong>
            <p>{a.blurb}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ── Interactive "Play Explained" — step through the same possession ── */
function PlayExplained() {
  const [step, setStep] = useState(0);
  const frame = PLAY[step];
  const agent = AGENTS[frame.agent];
  return (
    <section className="lp-section lp-explain">
      <span className="lp-kicker">See a play explained</span>
      <h2>Step through the possession.</h2>
      <div className="explain-wrap">
        <div className="explain-court" aria-hidden>
          <div className="court-line court-mid" />
          <div className="court-hoop court-hoop-r" />
          {frame.players.map((p, i) => (
            <div key={i} className="court-orb sm" style={{ left: `${p.x}%`, top: `${p.y}%` }} />
          ))}
          <div className="court-ball sm" style={{ left: `${frame.ball.x}%`, top: `${frame.ball.y}%` }} />
        </div>
        <div className="explain-panel">
          <span className={`explain-agent agent-${agent.id}`}>{agent.name}</span>
          <p className="explain-pbp">{frame.pbp}</p>
          <p className="explain-hud">{frame.hud}</p>
          <div className="explain-controls">
            <button className="cta-ghost" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>← Back</button>
            <span className="explain-count">{step + 1} / {PLAY.length}</span>
            <button className="cta-ghost" disabled={step === PLAY.length - 1} onClick={() => setStep((s) => s + 1)}>Next →</button>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Feature teasers ── */
function Teasers() {
  return (
    <section className="lp-section">
      <span className="lp-kicker">What you get</span>
      <h2>A personalized sports desk.</h2>
      <div className="teaser-grid">
        <Link to="/dream-team" className="teaser teaser-dream">
          <span className="teaser-tag">Dream Team</span>
          <strong>Simulate 10,000 seasons.</strong>
          <p>Draft real stars, get championship odds, a projected record, and a shareable result card.</p>
          <div className="teaser-mock dream-mock">
            <div className="dm-ring"><span>34%</span></div>
            <div className="dm-bars"><i style={{ height: "30%" }} /><i style={{ height: "55%" }} /><i style={{ height: "80%" }} /><i className="hot" style={{ height: "62%" }} /></div>
          </div>
          <span className="teaser-go">Open the lab →</span>
        </Link>

        <div className="teaser teaser-qa">
          <span className="teaser-tag">Ask during live games</span>
          <strong>Pause and ask anything.</strong>
          <p>Interrupt a reel or game and ask why a call happened — agents answer with the rulebook and box score.</p>
          <div className="teaser-mock qa-mock">
            <div className="qa-bubble user">Was that a legal screen?</div>
            <div className="qa-bubble ai"><b>RefAgent:</b> Yes — the screener was set and stationary. Legal.</div>
          </div>
        </div>

        <div className="teaser teaser-reel">
          <span className="teaser-tag">Personalized reels</span>
          <strong>Pulse · Story · Deep Cut.</strong>
          <p>Narrated highlight reels in 2, 5, or 10 minutes — with overlays and interrupt-and-ask built in.</p>
          <div className="teaser-mock reel-mock">
            <span className="reel-tier on">Pulse</span><span className="reel-tier">Story</span><span className="reel-tier">Deep Cut</span>
          </div>
        </div>

        <div className="teaser teaser-board">
          <span className="teaser-tag">Leaderboard</span>
          <strong>Climb with picks &amp; titles.</strong>
          <p>Pick'em streaks and Dream Team titles rank you against everyone.</p>
          <div className="teaser-mock board-mock">
            {[["1", "You", "1,280"], ["2", "courtvision", "1,140"], ["3", "hoopla", "990"]].map(([r, n, p]) => (
              <div key={r} className={`board-row ${n === "You" ? "me" : ""}`}><span>{r}</span><b>{n}</b><i>{p}</i></div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  return (
    <main className="lp">
      <CourtHero />
      <MeetTheAgents />
      <PlayExplained />
      <Teasers />

      <section className="lp-section lp-final">
        <span className="lp-kicker">No signup. No friction.</span>
        <h2>Pick your team. The agents do the rest.</h2>
        <p>Choose your leagues, teams, and stars — ReplaysAI builds your feed, reels, and simulations instantly. Nothing to sign up for.</p>
        <Link to="/onboarding" className="cta-primary big">Assemble Your Squad</Link>
        <div className="lp-divider"><span>or get product updates</span></div>
        <Waitlist />
      </section>
    </main>
  );
}
