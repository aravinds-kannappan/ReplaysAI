import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { apiPath } from "../lib/api";
import HeroPlayShowcase from "../components/HeroPlayShowcase";
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
          <HeroPlayShowcase />
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
