import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { apiPath } from "../lib/api";
import "./Landing.css";

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
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" aria-label="Email for waitlist" />
      <button type="submit" disabled={status === "loading"}>{status === "loading" ? "Joining…" : "Get updates"}</button>
      {status === "ok" && <p className="waitlist-msg ok">{message}</p>}
      {status === "error" && <p className="waitlist-msg error">{message}</p>}
    </form>
  );
}

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
      // Court lines
      ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 1;
      ctx.strokeRect(W * 0.04, H * 0.08, W * 0.92, H * 0.84);
      ctx.beginPath(); ctx.moveTo(W / 2, H * 0.08); ctx.lineTo(W / 2, H * 0.92); ctx.stroke();
      ctx.beginPath(); ctx.arc(W / 2, H / 2, Math.min(W, H) * 0.12, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = "rgba(45,140,255,0.3)";
      ctx.beginPath(); ctx.arc(W * 0.94, H / 2, 4, 0, Math.PI * 2); ctx.stroke();
      // Defenders (dim)
      for (const p of off) {
        const q = posAt(p, t + 0.7);
        ctx.fillStyle = "rgba(100,120,140,0.25)";
        ctx.beginPath(); ctx.arc(q.x + 14, q.y - 10, 5, 0, Math.PI * 2); ctx.fill();
      }
      // Ball pass
      passT += dt;
      if (passT > 1.8) { passT = 0; prevHolder = holder; holder = (holder + 1 + Math.floor(Math.random() * 2)) % off.length; }
      const e = Math.min(1, passT / 1.0);
      const ease = e < 0.5 ? 2 * e * e : 1 - Math.pow(-2 * e + 2, 2) / 2;
      const a = posAt(off[prevHolder], t), b = posAt(off[holder], t);
      const ball = { x: a.x + (b.x - a.x) * ease, y: a.y + (b.y - a.y) * ease };
      // Offensive orbs
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
      // Ball trail
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
      // Scan line
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
      {["scout","stat","ref","predict"].map((id, i) => {
        const labels = ["Scout", "Stat", "Ref", "Predict"];
        const active = labels[i] === frame.agent;
        const values = ["Player spacing · pace +12", "9-2 run · 3PT 41%", "Verticality — legal", `${wp}% win prob`];
        return (
          <div key={id} className={`court-hud hud-${id} ${active ? "active" : ""}`}>
            <span className="hud-tag">{labels[i]}Agent</span>
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

const FEATURES = [
  { icon: "📡", title: "Live tracking", desc: "Four AI agents watch every possession simultaneously — scout, stats, rules, and win probability." },
  { icon: "🎬", title: "AI Reel Director", desc: "Tell the AI what reel you want in plain language. 2-min pulse, 5-min story, or 10-min deep cut." },
  { icon: "🎙️", title: "Broadcast mode", desc: "Two-host AI podcast about any game — like NotebookLM for sports. Plays in your browser." },
  { icon: "📰", title: "Weekly newsletter", desc: "Personalized digest for your teams and followed players, generated fresh every week." },
  { icon: "🏆", title: "Dream Team Sim", desc: "Draft real stars and run 10,000 Monte-Carlo seasons for championship odds." },
  { icon: "🎯", title: "Pick'em & leaderboard", desc: "Make game picks, track your streak, and climb the leaderboard against everyone." },
];

export default function Landing() {
  return (
    <main className="lp">
      {/* Nav */}
      <nav className="lp-nav">
        <Link to="/" className="lp-nav-brand">
          <img src="/replaysai-logo.svg" alt="ReplaysAI" />
          Replays<b>AI</b>
        </Link>
        <div className="lp-nav-links">
          <a href="#features" className="lp-nav-link">Features</a>
          <a href="#how" className="lp-nav-link">How it works</a>
          <Link to="/onboarding" className="cta-primary" style={{ padding: "9px 18px", fontSize: "0.88rem" }}>Get started</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="lp-hero">
        <div className="lp-hero-copy">
          <span className="lp-eyebrow">AI sports intelligence</span>
          <h1>Your teams.<br />Your stats.<br /><em>Your feed.</em></h1>
          <p className="lp-hero-desc">
            Four AI agents track every game for your teams — live scores, player stats for every position,
            narrated reels, and a weekly digest. No signup. Just pick your teams and go.
          </p>
          <div className="lp-hero-actions">
            <Link to="/onboarding" className="cta-primary big">Pick your teams</Link>
            <a href="#features" className="cta-ghost">See what's included</a>
          </div>
          <div className="lp-hero-meta">
            <span><strong>NBA + NFL</strong> covered</span>
            <span><strong>Free</strong> to use</span>
            <span><strong>No</strong> signup needed</span>
          </div>
        </div>
        <CourtPanel />
      </section>

      {/* Stats strip */}
      <div className="stat-strip">
        {[["2 leagues", "NBA + NFL live data"], ["All positions", "QB, RB, WR, TE, D, NBA all"], ["4 AI agents", "Scout, Stat, Ref, Predict"], ["1 click", "Pick teams, get your feed"]].map(([v, l]) => (
          <div key={v} className="stat-strip-item">
            <span className="stat-strip-value">{v}</span>
            <span className="stat-strip-label">{l}</span>
          </div>
        ))}
      </div>

      {/* Features */}
      <section className="lp-section" id="features">
        <div className="lp-section-header">
          <span className="lp-label">Everything included</span>
          <h2>A full sports desk in your browser.</h2>
          <p>Live scores, deep stats for every player position, AI reels, broadcast podcasts, a weekly newsletter — all personalized to your teams.</p>
        </div>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature-card">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="lp-section" id="how">
        <div className="lp-section-header">
          <span className="lp-label">How it works</span>
          <h2>Up in under a minute.</h2>
        </div>
        <div className="how-steps">
          {[
            { n: "01", title: "Pick your teams", desc: "Select your NBA and NFL teams and a handful of star players to follow." },
            { n: "02", title: "Your feed builds", desc: "Scores, results, standings, and player stats filter instantly to your selections." },
            { n: "03", title: "Build a reel", desc: "Type what you want — last Celtics game, Jalen Brunson's buckets — and the AI builds it." },
            { n: "04", title: "Read your newsletter", desc: "Every week, a fresh personalized digest of your teams and players lands on your dashboard." },
          ].map((s) => (
            <div key={s.n} className="how-step">
              <span className="how-num">{s.n}</span>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Teasers */}
      <section className="lp-section">
        <div className="lp-section-header">
          <span className="lp-label">Explore the tools</span>
          <h2>More than a scoreboard.</h2>
        </div>
        <div className="teaser-grid">
          <Link to="/dream-team" className="teaser teaser-dream">
            <span className="teaser-tag">Dream Team</span>
            <strong>Simulate 10,000 seasons.</strong>
            <p>Draft real stars, get championship odds, a projected record, and a shareable result card.</p>
            <div className="teaser-mock">
              <div className="dm-ring">34%</div>
              <div className="dm-bars"><i style={{ height: "30%" }} /><i style={{ height: "55%" }} /><i style={{ height: "80%" }} /><i className="hot" style={{ height: "62%" }} /></div>
            </div>
            <span className="teaser-go">Open the lab →</span>
          </Link>
          <div className="teaser">
            <span className="teaser-tag">Ask during live games</span>
            <strong>Pause and ask anything.</strong>
            <p>Interrupt a reel and ask why a call happened — agents answer with the rulebook and box score.</p>
            <div className="teaser-mock qa-mock">
              <div className="qa-bubble user">Was that a legal screen?</div>
              <div className="qa-bubble ai"><b>RefAgent:</b> Yes — the screener was set and stationary. Legal.</div>
            </div>
          </div>
          <div className="teaser">
            <span className="teaser-tag">Personalized reels</span>
            <strong>Pulse · Story · Deep Cut.</strong>
            <p>Narrated highlight reels in 2, 5, or 10 minutes with broadcast AI voices built in.</p>
            <div className="teaser-mock reel-mock">
              <span className="reel-tier on">Pulse</span><span className="reel-tier">Story</span><span className="reel-tier">Deep Cut</span>
            </div>
          </div>
          <div className="teaser">
            <span className="teaser-tag">Leaderboard</span>
            <strong>Climb with picks.</strong>
            <p>Pick'em streaks and Dream Team titles rank you against everyone.</p>
            <div className="teaser-mock board-mock">
              {[["1", "You", "1,280"], ["2", "courtvision", "1,140"], ["3", "hoopla", "990"]].map(([r, n, p]) => (
                <div key={r} className={`board-row ${n === "You" ? "me" : ""}`}><span>{r}</span><b>{n}</b><i>{p}</i></div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="lp-section lp-final">
        <span className="lp-label">No signup. No friction.</span>
        <h2>Pick your teams. Get your feed.</h2>
        <p>Choose your leagues, teams, and stars — ReplaysAI builds your personalized dashboard instantly.</p>
        <Link to="/onboarding" className="cta-primary big">Get started free</Link>
        <div className="lp-divider"><span>or stay in the loop</span></div>
        <Waitlist />
      </section>
    </main>
  );
}
