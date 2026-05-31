import { Link } from "react-router-dom";
import { SignedIn, SignedOut } from "@clerk/clerk-react";
import "./Landing.css";

const STATS = [
  { value: "5,597+", label: "Plays Tracked" },
  { value: "5", label: "Seasons" },
  { value: "4", label: "AI Agents" },
  { value: "2", label: "Sports" },
];

const POINTS_ROWS = [
  ["Correct prediction", "+100"],
  ["Spread within 5 pts", "+150"],
  ["Daily login", "+5"],
  ["7-day streak bonus", "+25"],
];

export default function Landing() {
  return (
    <div className="landing">
      {/* Animated orb blobs */}
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />
      <div className="orb orb-4" />

      {/* Floating particles */}
      <div className="particles">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="particle" />
        ))}
      </div>

      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="hero-section">
        <div className="hero-eyebrow">
          <span className="eyebrow-dot" />
          NBA · NFL · Multimodal AI
        </div>

        <h1 className="hero-title">
          The sports platform
          <span className="line-2">built for real fans.</span>
        </h1>

        <p className="hero-sub">
          Real play-by-play data. Computer vision. LLMs that write from your
          team's perspective. Predictions that earn you points. One platform
          that finally gets it.
        </p>

        <div className="hero-ctas">
          <SignedOut>
            <Link to="/sign-up" className="btn-hero-primary">
              Get Started Free →
            </Link>
            <Link to="/sign-in" className="btn-hero-ghost">
              Sign In
            </Link>
          </SignedOut>
          <SignedIn>
            <Link to="/feed" className="btn-hero-primary">
              Go to My Feed →
            </Link>
          </SignedIn>
        </div>

        {/* Live stats row */}
        <div className="hero-stats">
          {STATS.map((s) => (
            <div key={s.label} className="stat-pill">
              <span className="stat-pill-value">{s.value}</span>
              <span className="stat-pill-label">{s.label}</span>
            </div>
          ))}
        </div>

        <div className="scroll-hint">
          <span>Scroll</span>
          <div className="scroll-arrow" />
        </div>
      </section>

      {/* ── Feature Bento Grid ───────────────────────────── */}
      <section className="features-section">
        <div className="section-label">What you get</div>
        <h2>Everything a serious fan needs</h2>

        <div className="features-bento">
          {/* Card 1 — AI Pipeline (wide) */}
          <div className="bento-card wide accent-orange">
            <span className="bento-icon">🤖</span>
            <h3>3-Agent AI Recap Pipeline</h3>
            <p>
              Three specialized agents run in parallel — statistical event
              extraction, computer vision play classification, and LLM
              summarization — so your recap is ready in seconds, not minutes.
            </p>
            <div className="pipeline-viz">
              <span className="pipe-step s1">Event Extraction</span>
              <span className="pipe-arrow">→</span>
              <span className="pipe-step s2">CV Classification</span>
              <span className="pipe-arrow">→</span>
              <span className="pipe-step s3">LLM Summary</span>
              <span className="pipe-arrow">→</span>
              <span className="pipe-step s4">Fan Perspective</span>
            </div>
          </div>

          {/* Card 2 — Fan Mode (tall) */}
          <div className="bento-card tall accent-purple">
            <span className="bento-icon">🏀</span>
            <h3>Fan Mode</h3>
            <p>
              Every recap rewritten from your team's exact perspective.
              Wins land with energy. Losses get an honest post-mortem.
              Powered by Claude Sonnet — cached so it's instant on revisit.
            </p>
            <div style={{ marginTop: 20 }}>
              <div className="pipe-step s3" style={{ display: "inline-block", marginBottom: 8 }}>
                Generic recap in
              </div>
              <div style={{ fontSize: "1.4rem", margin: "4px 0" }}>↓</div>
              <div className="pipe-step s4" style={{ display: "inline-block" }}>
                Your team's story out
              </div>
            </div>
          </div>

          {/* Card 3 — Predictions (half) */}
          <div className="bento-card half accent-pink">
            <span className="bento-icon">🎯</span>
            <h3>Predictions</h3>
            <p>
              Pick game winners before tipoff. Add a spread prediction for
              bonus points. Auto-scored when the game goes final.
            </p>
          </div>

          {/* Card 4 — Points (half) */}
          <div className="bento-card half accent-blue">
            <span className="bento-icon">⭐</span>
            <h3>Points & Streaks</h3>
            <div className="points-list">
              {POINTS_ROWS.map(([action, pts]) => (
                <div key={action} className="points-row">
                  <span>{action}</span>
                  <span>{pts} pts</span>
                </div>
              ))}
            </div>
          </div>

          {/* Card 5 — Real Data (third) */}
          <div className="bento-card third">
            <span className="bento-icon">📊</span>
            <h3>Real Data</h3>
            <p>
              5+ seasons of NBA & NFL play-by-play. Every dunk, block, TD,
              and interception — not mock data.
            </p>
          </div>

          {/* Card 6 — Leaderboard (third) */}
          <div className="bento-card third accent-orange">
            <span className="bento-icon">🏆</span>
            <h3>Leaderboard</h3>
            <p>
              Global rankings by prediction accuracy and points. Badges for
              streaks, clutch picks, and consistent engagement.
            </p>
          </div>

          {/* Card 7 — Roster (third) */}
          <div className="bento-card third accent-purple">
            <span className="bento-icon">📋</span>
            <h3>Roster Builder</h3>
            <p>
              Pick 8 players each week. Impact scores drawn from real
              play-by-play stats — not projections.
            </p>
          </div>
        </div>
      </section>

      {/* ── How it works timeline ────────────────────────── */}
      <section className="how-section">
        <div className="section-label">Under the hood</div>
        <h2>Powered by multimodal AI</h2>

        <div className="how-timeline">
          <div className="how-step">
            <div className="how-num how-num-1">01</div>
            <h4>Ingest</h4>
            <p>
              ESPN play-by-play lands in PostgreSQL. Every dunk and
              fourth-quarter stop, structured and indexed.
            </p>
          </div>
          <div className="how-step">
            <div className="how-num how-num-2">02</div>
            <h4>Extract</h4>
            <p>
              Agent 1 computes momentum shifts, clutch moments, and
              top-performer impact scores in pure Python — no LLM cost.
            </p>
          </div>
          <div className="how-step">
            <div className="how-num how-num-3">03</div>
            <h4>See</h4>
            <p>
              Agent 2 downloads highlight video, extracts frames via OpenCV,
              and classifies plays with Claude Vision.
            </p>
          </div>
          <div className="how-step">
            <div className="how-num how-num-4">04</div>
            <h4>Tell</h4>
            <p>
              Agent 3 runs 4 parallel LLM calls, assembles a full recap,
              then Agent 4 rewrites it for your team's fans.
            </p>
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────── */}
      <section className="cta-section">
        <div className="cta-card">
          <h2>Your team deserves better recaps.</h2>
          <p>
            No credit card. Pick your team in 60 seconds.
            Personalized feed starts immediately.
          </p>
          <div className="cta-badges">
            {["🎯 Smart Predictions", "🏀 Fan Mode Recaps", "🏆 Live Leaderboard", "📊 Real Play Data"].map((b) => (
              <span key={b} className="cta-badge">{b}</span>
            ))}
          </div>
          <SignedOut>
            <Link to="/sign-up" className="btn-hero-primary">
              Create Free Account
            </Link>
          </SignedOut>
          <SignedIn>
            <Link to="/feed" className="btn-hero-primary">
              Go to My Feed →
            </Link>
          </SignedIn>
        </div>
      </section>

      <footer className="landing-footer">
        Replays AI · Built with Claude Sonnet + Computer Vision
      </footer>
    </div>
  );
}
