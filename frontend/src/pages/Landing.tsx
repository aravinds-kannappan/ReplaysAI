import { Link } from "react-router-dom";
import { SignedIn, SignedOut } from "@clerk/clerk-react";
import "./Landing.css";

const STATS = [
  { value: "400K+", label: "Plays Tracked" },
  { value: "5", label: "Seasons" },
  { value: "4", label: "AI Agents" },
  { value: "2", label: "Sports" },
];

const FEATURES = [
  {
    icon: "🤖",
    title: "Multi-Agent AI Pipeline",
    desc: "Three specialized agents run in parallel via asyncio — event extraction, computer vision play classification with Claude Vision, and LLM summarization. Full recap in seconds, not minutes.",
    accent: "orange",
    tags: ["asyncio.gather", "Claude Vision", "OpenCV"],
  },
  {
    icon: "🏀",
    title: "Fan Mode Recaps",
    desc: "Pick any game your team played. Claude rewrites the recap from your team's exact perspective — wins land with energy, losses get an honest post-mortem. Cached permanently after first generation.",
    accent: "purple",
    tags: ["Claude Sonnet", "Redis cache", "On-demand"],
  },
  {
    icon: "🎯",
    title: "Predictions + Points",
    desc: "Pick game winners before tipoff across NBA and NFL. Add a spread prediction for bonus points. Every pick is auto-scored when the game goes final.",
    accent: "pink",
    tags: ["Auto-scored", "Spread bonus", "Both sports"],
  },
  {
    icon: "🏆",
    title: "Global Leaderboard",
    desc: "Global ranking by prediction points. Badges for streaks, clutch picks, and consistent engagement. Your rank widget shows exactly where you stand among all users.",
    accent: "blue",
    tags: ["Global rank", "7 badges", "Streak tracking"],
  },
  {
    icon: "📋",
    title: "Weekly Roster Builder",
    desc: "Pick up to 8 players per week from NBA or NFL rosters. Impact scores are computed from real play-by-play stats — every dunk, block, touchdown, and sack counts.",
    accent: "green",
    tags: ["Real stats", "NBA + NFL", "8 players"],
  },
  {
    icon: "📊",
    title: "Real ESPN Data",
    desc: "5+ seasons of NBA and NFL play-by-play from ESPN. 17-table PostgreSQL schema covering teams, players, games, plays, box scores, CV outputs, recaps, and the full user layer.",
    accent: "orange",
    tags: ["5 seasons", "17 tables", "No mock data"],
  },
];

const HOW_STEPS = [
  {
    num: "01",
    cls: "how-num-1",
    title: "Ingest",
    desc: "ESPN play-by-play lands in PostgreSQL every 60 seconds during game hours — every dunk, stop, and fourth-quarter drive, structured and indexed.",
  },
  {
    num: "02",
    cls: "how-num-2",
    title: "Extract",
    desc: "Agent 1 computes momentum shifts, clutch moments, and top-performer impact scores in pure Python with no LLM cost — runs instantly.",
  },
  {
    num: "03",
    cls: "how-num-3",
    title: "See",
    desc: "Agent 2 downloads highlight video via yt-dlp, extracts frames with OpenCV, and classifies 14 play types using Claude Vision batch inference.",
  },
  {
    num: "04",
    cls: "how-num-4",
    title: "Tell",
    desc: "Agent 3 runs 4 parallel Claude calls for a structured recap. Agent 4 rewrites it from your team's fan perspective, cached permanently after first generation.",
  },
];

const POINTS_ROWS = [
  ["Correct prediction", "+100 pts"],
  ["Spread within 5 pts", "+150 pts"],
  ["Daily login", "+5 pts"],
  ["7-day streak bonus", "+25 pts"],
  ["First prediction of week", "+10 pts"],
];

const BADGES = ["🎯 First Pick", "🔮 Oracle", "🔥 Loyal Fan", "🏆 Superfan", "📊 Analyst", "⏱️ Clutch"];

const TECH = [
  { name: "FastAPI", color: "#009688" },
  { name: "PostgreSQL 16", color: "#336791" },
  { name: "Redis 7", color: "#DC382D" },
  { name: "Claude Sonnet 4.6", color: "#8b5cf6" },
  { name: "React 18", color: "#61DAFB" },
  { name: "TypeScript", color: "#3178C6" },
  { name: "Clerk Auth", color: "#6C47FF" },
  { name: "OpenCV", color: "#5C8A32" },
  { name: "yt-dlp", color: "#f59e0b" },
  { name: "SQLAlchemy 2.0", color: "#B22222" },
  { name: "Vite 8", color: "#646CFF" },
  { name: "Vercel", color: "#ffffff" },
];

function MockGameCard() {
  return (
    <div className="mock-card">
      <div className="mock-card-header">
        <span className="mock-sport-badge">🏀 NBA</span>
        <span className="mock-status final">Final</span>
      </div>
      <div className="mock-card-teams">
        <div className="mock-team">
          <span className="mock-abbr">BOS</span>
          <span className="mock-score winner">112</span>
        </div>
        <span className="mock-vs">vs</span>
        <div className="mock-team">
          <span className="mock-abbr">MIA</span>
          <span className="mock-score">98</span>
        </div>
      </div>
      <div className="mock-recap-preview">
        "Jayson Tatum's 34-point fourth quarter sealed a dominant Celtics win. Boston's defense held Miami to 18 points in the final frame, forcing six turnovers in the clutch..."
      </div>
      <div className="mock-card-actions">
        <span className="mock-action-btn purple">🏀 Fan Mode</span>
        <span className="mock-action-btn orange">🎯 Predict Next</span>
      </div>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="landing">
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />
      <div className="orb orb-4" />
      <div className="particles">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="particle" />
        ))}
      </div>

      {/* ── Hero ── */}
      <section className="hero-section">
        <div className="hero-eyebrow">
          <span className="eyebrow-dot" />
          NBA · NFL · Multimodal AI
        </div>

        <h1 className="hero-title">
          Your sports platform.
          <span className="line-2">Finally built right.</span>
        </h1>

        <p className="hero-sub">
          Real ESPN play-by-play. Computer vision highlights. Claude-powered recaps written from
          your team's exact perspective. Predictions that earn you points on a global leaderboard.
          NBA and NFL — five seasons of real data, zero mock data.
        </p>

        <div className="hero-ctas">
          <SignedOut>
            <Link to="/sign-up" className="btn-hero-primary">Get Started Free →</Link>
            <Link to="/sign-in" className="btn-hero-ghost">Sign In</Link>
          </SignedOut>
          <SignedIn>
            <Link to="/feed" className="btn-hero-primary">Go to My Feed →</Link>
          </SignedIn>
        </div>

        <div className="hero-stats">
          {STATS.map((s) => (
            <div key={s.label} className="stat-pill">
              <span className="stat-pill-value">{s.value}</span>
              <span className="stat-pill-label">{s.label}</span>
            </div>
          ))}
        </div>

        <div className="hero-preview-wrap">
          <MockGameCard />
        </div>

        <div className="scroll-hint">
          <span>Scroll</span>
          <div className="scroll-arrow" />
        </div>
      </section>

      {/* ── Sports coverage banner ── */}
      <section className="sports-banner">
        <div className="sports-banner-inner">
          <span className="sports-label-text">Live coverage for</span>
          <div className="sport-badge-pill nba">🏀 NBA</div>
          <span className="sports-and">+</span>
          <div className="sport-badge-pill nfl">🏈 NFL</div>
          <span className="sports-label-text">· 5 seasons · real ESPN data · updated every 60 seconds</span>
        </div>
      </section>

      {/* ── Features grid ── */}
      <section className="features-section">
        <div className="section-label">What you get</div>
        <h2>Six features. Zero filler.</h2>
        <p className="section-sub">
          Everything is backed by real data, real AI agents, and real ESPN play-by-play.
          Nothing is mocked up, projected, or estimated.
        </p>

        <div className="features-grid-6">
          {FEATURES.map((f) => (
            <div key={f.title} className={`feat-card accent-${f.accent}`}>
              <span className="feat-icon">{f.icon}</span>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
              <div className="feat-tags">
                {f.tags.map((t) => <span key={t} className="feat-tag">{t}</span>)}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pipeline ── */}
      <section className="pipeline-section">
        <div className="section-label">Under the hood</div>
        <h2>Four agents. One recap.</h2>
        <p className="section-sub">
          The most expensive steps — CV inference and LLM generation — run concurrently via{" "}
          <code className="inline-code">asyncio.gather()</code>. Sub-second retrieval on repeat
          visits thanks to Redis permanent caching.
        </p>

        <div className="how-timeline">
          {HOW_STEPS.map((s) => (
            <div key={s.num} className="how-step">
              <div className={`how-num ${s.cls}`}>{s.num}</div>
              <h4>{s.title}</h4>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Points & Badges ── */}
      <section className="points-section">
        <div className="points-inner">
          <div className="points-left">
            <div className="section-label">Gamification</div>
            <h2>Every action earns points.</h2>
            <p>
              Pick games before tipoff, predict the spread for bonus points, log in daily,
              build streaks. Points accumulate on a global leaderboard with six badges to earn
              for consistency, clutch picks, and engagement.
            </p>
            <div className="badges-row">
              {BADGES.map((b) => (
                <span key={b} className="badge-chip">{b}</span>
              ))}
            </div>
          </div>
          <div className="points-right">
            <div className="points-table-card">
              <div className="points-table-header">Action → Points</div>
              {POINTS_ROWS.map(([action, pts]) => (
                <div key={action} className="points-row-item">
                  <span>{action}</span>
                  <span className="pts-val">{pts}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Tech stack ── */}
      <section className="tech-section">
        <div className="section-label">Stack</div>
        <h2>A serious stack for a serious platform.</h2>
        <p className="section-sub">
          17-table PostgreSQL schema. Async FastAPI backend. Redis permanent caching.
          Claude Sonnet 4.6 for text and vision. Clerk JWT auth. Deployed on Vercel.
        </p>
        <div className="tech-chips">
          {TECH.map((t) => (
            <span
              key={t.name}
              className="tech-chip"
              style={{ borderColor: t.color + "55", color: t.color }}
            >
              {t.name}
            </span>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="cta-section">
        <div className="cta-card">
          <h2>Your team deserves better recaps.</h2>
          <p>Free forever. Pick your teams in 60 seconds. Personalized feed starts immediately.</p>
          <div className="cta-badges">
            {["🎯 Smart Predictions", "🏀🏈 NBA + NFL", "🏆 Leaderboard", "📊 Real Play Data"].map((b) => (
              <span key={b} className="cta-badge">{b}</span>
            ))}
          </div>
          <SignedOut>
            <Link to="/sign-up" className="btn-hero-primary">Create Free Account</Link>
          </SignedOut>
          <SignedIn>
            <Link to="/feed" className="btn-hero-primary">Go to My Feed →</Link>
          </SignedIn>
        </div>
      </section>

      <footer className="landing-footer">
        Replays AI · NBA + NFL · Claude Sonnet 4.6 · Computer Vision · Real ESPN Data
      </footer>
    </div>
  );
}
