import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { apiPath } from "../lib/api";
import "./Landing.css";

/* ── Waitlist ── */
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
      if (res.data?.status === "ok") { setStatus("ok"); setMessage(res.data.message || "You're on the list."); setEmail(""); }
      else { setStatus("error"); setMessage(res.data?.message || "Please enter a valid email."); }
    } catch { setStatus("error"); setMessage("Could not reach the waitlist service. Try again."); }
  }
  return (
    <form className="waitlist" onSubmit={submit}>
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" aria-label="Email for updates" />
      <button type="submit" disabled={status === "loading"}>{status === "loading" ? "Joining…" : "Get updates"}</button>
      {status === "ok" && <p className="waitlist-msg ok">{message}</p>}
      {status === "error" && <p className="waitlist-msg error">{message}</p>}
    </form>
  );
}

/* ── Hero court canvas: four agents tracking a live possession ── */
type Pt = { x: number; y: number };
const OFF_ZONES: Pt[] = [
  { x: 0.26, y: 0.5 }, { x: 0.46, y: 0.24 }, { x: 0.5, y: 0.78 },
  { x: 0.68, y: 0.46 }, { x: 0.78, y: 0.66 },
];
const PHASES = [
  { agent: "Scout", pbp: "Defensive board — guard ignites the break.", wp: 58 },
  { agent: "Stat", pbp: "Swing to the wing, defense scrambles to rotate.", wp: 63 },
  { agent: "Ref", pbp: "Drive draws the help — legal verticality, no foul.", wp: 66 },
  { agent: "Predict", pbp: "Kick-out to the corner, catch and rise…", wp: 71 },
  { agent: "Predict", pbp: "Corner three splashes — the lead extends.", wp: 78 },
];

function useCourtCanvas(canvasRef: React.RefObject<HTMLCanvasElement | null>) {
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
    const off = OFF_ZONES.map((z, i) => ({ ...z, sx: 0.6 + i * 0.07, sy: 0.7 + i * 0.09, px: i * 1.2, py: i * 0.8 }));
    const posAt = (p: typeof off[number], t: number) => ({
      x: (p.x + 0.06 * Math.sin(t * p.sx + p.px)) * W,
      y: (p.y + 0.07 * Math.cos(t * p.sy + p.py)) * H,
    });
    const trail: Pt[] = [];
    let holder = 0, prevHolder = 0, passT = 0, t = 0, raf = 0, last = performance.now();
    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now; t += dt;
      ctx.clearRect(0, 0, W, H);
      ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 1;
      ctx.strokeRect(W * 0.04, H * 0.08, W * 0.92, H * 0.84);
      ctx.beginPath(); ctx.moveTo(W / 2, H * 0.08); ctx.lineTo(W / 2, H * 0.92); ctx.stroke();
      ctx.beginPath(); ctx.arc(W / 2, H / 2, Math.min(W, H) * 0.12, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = "rgba(45,140,255,0.3)";
      ctx.beginPath(); ctx.arc(W * 0.94, H / 2, 4, 0, Math.PI * 2); ctx.stroke();
      for (const p of off) {
        const q = posAt(p, t + 0.7);
        ctx.fillStyle = "rgba(100,120,140,0.25)";
        ctx.beginPath(); ctx.arc(q.x + 14, q.y - 10, 5, 0, Math.PI * 2); ctx.fill();
      }
      passT += dt;
      if (passT > 1.8) { passT = 0; prevHolder = holder; holder = (holder + 1 + Math.floor(Math.random() * 2)) % off.length; }
      const e = Math.min(1, passT / 1.0);
      const ease = e < 0.5 ? 2 * e * e : 1 - Math.pow(-2 * e + 2, 2) / 2;
      const a = posAt(off[prevHolder], t), b = posAt(off[holder], t);
      const ball = { x: a.x + (b.x - a.x) * ease, y: a.y + (b.y - a.y) * ease };
      for (let i = 0; i < off.length; i++) {
        const p = posAt(off[i], t);
        const isH = i === holder;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, isH ? 20 : 14);
        g.addColorStop(0, "rgba(220,240,255,0.95)");
        g.addColorStop(0.35, "rgba(45,140,255,0.85)");
        g.addColorStop(1, "rgba(45,140,255,0)");
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(p.x, p.y, isH ? 20 : 14, 0, Math.PI * 2); ctx.fill();
      }
      trail.push({ ...ball }); if (trail.length > 16) trail.shift();
      for (let i = 0; i < trail.length; i++) {
        ctx.fillStyle = `rgba(249,115,22,${(i / trail.length) * 0.45})`;
        ctx.beginPath(); ctx.arc(trail[i].x, trail[i].y, 1.5 + (i / trail.length) * 3.5, 0, Math.PI * 2); ctx.fill();
      }
      const bg = ctx.createRadialGradient(ball.x, ball.y, 0, ball.x, ball.y, 10);
      bg.addColorStop(0, "rgba(255,240,200,1)");
      bg.addColorStop(1, "rgba(249,115,22,0)");
      ctx.fillStyle = bg;
      ctx.beginPath(); ctx.arc(ball.x, ball.y, 10, 0, Math.PI * 2); ctx.fill();
      const scanX = ((t * 0.1) % 1) * W;
      const sg = ctx.createLinearGradient(scanX - 30, 0, scanX + 30, 0);
      sg.addColorStop(0, "rgba(45,140,255,0)");
      sg.addColorStop(0.5, "rgba(45,140,255,0.07)");
      sg.addColorStop(1, "rgba(45,140,255,0)");
      ctx.fillStyle = sg; ctx.fillRect(scanX - 30, 0, 60, H);
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [canvasRef]);
}

function CourtPanel() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [phase, setPhase] = useState(0);
  const [wp, setWp] = useState(54);
  useCourtCanvas(canvasRef);

  useEffect(() => {
    const id = window.setInterval(() => setPhase((p) => (p + 1) % PHASES.length), 3200);
    return () => window.clearInterval(id);
  }, []);
  useEffect(() => {
    const target = PHASES[phase].wp;
    const id = window.setInterval(() => setWp((v) => Math.abs(target - v) < 1 ? target : v + Math.sign(target - v)), 40);
    return () => window.clearInterval(id);
  }, [phase]);

  const frame = PHASES[phase];
  return (
    <div className="lp-court-panel">
      <canvas ref={canvasRef} className="court-canvas" />
      {["scout", "stat", "ref", "predict"].map((id, i) => {
        const labels = ["Scout", "Stat", "Ref", "Predict"];
        const active = labels[i] === frame.agent;
        const values = ["Spacing · pace +12", "9-2 run · 3PT 41%", "Verticality — legal", `${wp}% win prob`];
        return (
          <div key={id} className={`court-hud hud-${id} ${active ? "active" : ""}`}>
            <span className="hud-tag">{labels[i]}</span>
            <strong className="hud-value">{values[i]}</strong>
          </div>
        );
      })}
      <div className="court-ticker">
        <span className="ticker-live">● LIVE</span>
        <span className="ticker-text" key={phase}>{frame.pbp}</span>
        <span className="ticker-clock">Q4 · 4:12</span>
      </div>
    </div>
  );
}

/* ── Live score marquee (real ESPN finals, graceful fallback) ── */
type TickGame = { id: number; sport: string; status: string; away_team?: { abbreviation?: string }; home_team?: { abbreviation?: string }; away_score?: number | null; home_score?: number | null };
function ScoreMarquee() {
  const [games, setGames] = useState<TickGame[]>([]);
  useEffect(() => {
    let alive = true;
    axios.get(apiPath("/api/feed"), { params: { limit: 60 } })
      .then((r) => {
        if (!alive) return;
        const g = ((r.data?.games ?? []) as TickGame[]).filter((x) => x.status === "final" && x.away_score != null).slice(0, 16);
        setGames(g);
      })
      .catch(() => { /* decorative — hide on failure */ });
    return () => { alive = false; };
  }, []);
  if (games.length === 0) return null;
  const row = [...games, ...games];
  return (
    <div className="lp-marquee" aria-hidden>
      <div className="lp-marquee-track">
        {row.map((g, i) => (
          <span key={i} className="lp-tick">
            <i className="lp-tick-league">{g.sport}</i>
            <b>{g.away_team?.abbreviation}</b> {g.away_score}
            <span className="lp-tick-at">·</span>
            {g.home_score} <b>{g.home_team?.abbreviation}</b>
            <i className="lp-tick-f">F</i>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ── Scroll reveal ── */
function useReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
    if (!("IntersectionObserver" in window)) { els.forEach((el) => el.classList.add("in")); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.18 });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

/* ── Per-feature live mini-visuals (no cards — they bleed into the row) ── */
function AgentsViz() {
  const rows = [
    { name: "Scout", v: "spacing +12", w: 72 },
    { name: "Stat", v: "9-2 run · 41% 3PT", w: 88 },
    { name: "Ref", v: "legal verticality", w: 54 },
    { name: "Predict", v: "78% win prob", w: 78 },
  ];
  return (
    <div className="viz viz-agents">
      {rows.map((r, i) => (
        <div className="vz-agent" key={r.name} style={{ animationDelay: `${i * 0.12}s` }}>
          <span className="vz-dot" />
          <span className="vz-name">{r.name}</span>
          <span className="vz-bar"><i style={{ width: `${r.w}%` }} /></span>
          <span className="vz-val">{r.v}</span>
        </div>
      ))}
    </div>
  );
}
function ReelViz() {
  return (
    <div className="viz viz-reel">
      <div className="vz-reel-head"><span className="vz-reel-dot" /> Director</div>
      <div className="vz-reel-prompt">“every Brunson bucket this week”</div>
      <div className="vz-reel-track">
        <span className="seg s1" /><span className="seg s2" /><span className="seg s3" /><span className="seg s4" /><span className="seg s5" />
        <span className="vz-reel-play">▶</span>
      </div>
      <div className="vz-reel-tiers"><b>Pulse 2:00</b><span>Story 5:00</span><span>Deep Cut 10:00</span></div>
    </div>
  );
}
function BroadcastViz() {
  return (
    <div className="viz viz-cast">
      <div className="vz-hosts">
        <span className="vz-host vz-host-a">P</span>
        <span className="vz-host vz-host-b">A</span>
      </div>
      <div className="vz-wave">{Array.from({ length: 28 }).map((_, i) => <i key={i} style={{ animationDelay: `${(i % 14) * 0.07}s` }} />)}</div>
      <div className="vz-cast-cap">Two-host AI breakdown · plays in your browser</div>
    </div>
  );
}
function NewsletterViz() {
  return (
    <div className="viz viz-news">
      <div className="vz-news-mast">ReplaysAI Weekly</div>
      <div className="vz-news-line lg" />
      <div className="vz-news-line" /><div className="vz-news-line" /><div className="vz-news-line sm" />
      <div className="vz-news-chips"><span>BOS</span><span>KC</span><span>NYK</span></div>
    </div>
  );
}

const FEATURES = [
  { idx: "01", kicker: "Play breakdown", title: "Four agents break down the key plays.", body: "Tap any scoring play and Scout (alignment), Stat (the numbers), Ref (the rulebook) and Predict (a win-probability proxy) each weigh in. Transparent, rule-based reads — not a black box.", viz: <AgentsViz />, to: "/onboarding", cta: "See a breakdown" },
  { idx: "02", kicker: "Reel Director", title: "Describe the reel. It builds it.", body: "Type what you want in plain language — a team's last game, every bucket from one player — and get an animated, voiced recap. Game search is powered by Claude.", viz: <ReelViz />, to: "/reels", cta: "Open the director" },
  { idx: "03", kicker: "Broadcast mode", title: "A two-host podcast for any game.", body: "Play-by-play and analyst voices break down what happened and why — grounded in the real box score. NotebookLM, for sports.", viz: <BroadcastViz />, to: "/onboarding", cta: "Hear a broadcast" },
  { idx: "04", kicker: "Weekly newsletter", title: "Your week, written for your teams.", body: "Results, player stats across every position, hot takes and picks — generated fresh each week for the teams and players you follow.", viz: <NewsletterViz />, to: "/newsletter", cta: "Read an issue" },
];

const NUMBERS = [
  { v: "2", l: "leagues — NBA + NFL, live" },
  { v: "All", l: "positions — QB to safety, G to C" },
  { v: "4", l: "analysis agents per key play" },
  { v: "0", l: "logins — just pick your teams" },
];

const STEPS = [
  { n: "01", t: "Pick your teams", d: "Choose NBA and NFL teams and a few star players to follow." },
  { n: "02", t: "Your feed builds", d: "Scores, results, standings and player stats filter to your picks instantly." },
  { n: "03", t: "Make a reel", d: "Tell the director what to build — or launch a full broadcast." },
  { n: "04", t: "Read your week", d: "A personalized newsletter lands on your dashboard every week." },
];

export default function Landing() {
  useReveal();
  return (
    <main className="lp">
      {/* Nav */}
      <nav className="lp-nav">
        <Link to="/" className="lp-nav-brand">
          <img src="/replaysai-logo.svg" alt="" />
          Replays<b>AI</b>
        </Link>
        <div className="lp-nav-links">
          <a href="#features" className="lp-nav-link">Features</a>
          <a href="#how" className="lp-nav-link">How it works</a>
          <Link to="/onboarding" className="lp-nav-cta">Try the demo</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="lp-hero">
        <div className="lp-hero-grid">
          <div className="lp-hero-copy" data-reveal>
            <span className="lp-eyebrow"><span className="lp-eyebrow-dot" /> Your personalized sports desk</span>
            <h1>The game,<br /><span className="lp-grad">decoded</span> for<br />your teams.</h1>
            <p className="lp-hero-sub">
              Real ESPN data for the NBA and NFL teams you follow — every position, animated voiced reels,
              key-play breakdowns, in-browser broadcasts and a weekly digest. No signup. Pick your teams and go.
            </p>
            <div className="lp-cta-row">
              <Link to="/onboarding" className="lp-btn-primary">Pick your teams →</Link>
              <a href="#features" className="lp-btn-ghost">See what it does</a>
            </div>
            <div className="lp-hero-meta">
              <span><b>NBA + NFL</b> live</span>
              <span><b>Free</b> · no login</span>
              <span><b>Real</b> ESPN data</span>
            </div>
          </div>
          <CourtPanel />
        </div>
        <ScoreMarquee />
      </section>

      {/* Manifesto — big type, no cards */}
      <section className="lp-manifesto">
        <p data-reveal>Most apps give you <em>a scoreboard.</em></p>
        <p data-reveal>ReplaysAI gives you <span className="lp-grad">a full sports desk</span> — agents, reels,
          broadcasts, stats and a newsletter, tuned to the exact teams and players you follow.</p>
        <p data-reveal className="lp-manifesto-small">Every position. Every game. Every week.</p>
      </section>

      {/* Features — full-bleed alternating rows */}
      <section className="lp-features" id="features">
        {FEATURES.map((f) => (
          <article className="lp-feature" key={f.idx} data-reveal>
            <div className="lp-feature-text">
              <span className="lp-feature-idx">{f.idx}</span>
              <span className="lp-feature-kicker">{f.kicker}</span>
              <h2>{f.title}</h2>
              <p>{f.body}</p>
              <Link to={f.to} className="lp-feature-link">{f.cta} →</Link>
            </div>
            <div className="lp-feature-viz">{f.viz}</div>
          </article>
        ))}
      </section>

      {/* Numbers band — inline, hairline separators */}
      <section className="lp-numbers">
        {NUMBERS.map((n) => (
          <div className="lp-number" key={n.l} data-reveal>
            <b>{n.v}</b>
            <span>{n.l}</span>
          </div>
        ))}
      </section>

      {/* How it works — connected timeline */}
      <section className="lp-how" id="how">
        <h2 className="lp-how-title" data-reveal>Up and running in under a minute.</h2>
        <div className="lp-how-track">
          {STEPS.map((s) => (
            <div className="lp-step" key={s.n} data-reveal>
              <span className="lp-step-num">{s.n}</span>
              <h3>{s.t}</h3>
              <p>{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="lp-final">
        <div className="lp-final-glow" />
        <h2 data-reveal>Pick your teams.<br />Get your <span className="lp-grad">whole sports desk.</span></h2>
        <p data-reveal>No signup, no friction — your personalized dashboard builds instantly.</p>
        <Link to="/onboarding" className="lp-btn-primary big" data-reveal>Start free →</Link>
        <div className="lp-final-or" data-reveal><span>or get product updates</span></div>
        <div data-reveal><Waitlist /></div>
        <footer className="lp-footer">
          <span>Replays<b>AI</b></span>
          <span>Real ESPN data · NBA + NFL · {new Date().getFullYear()}</span>
        </footer>
      </section>
    </main>
  );
}
